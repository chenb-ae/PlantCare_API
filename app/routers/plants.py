from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import SERVER_TIMESTAMP, Query as FirestoreQuery
from app.config.firebase import db
from app.config.plant_constants import PLANT_PROFILES, PLANT_TYPES, PLACEMENTS
from app.models.schemas import ResponseModel, PlantCreateRequest, PlantUpdateRequest, PlantResponse
from app.routers.sensors import helper_ensure_default_sensors_exist
import datetime

router = APIRouter(prefix="/api/plants", tags=["Plant Management & History"])

def helper_get_latest_sensor_reading(plant_id: str):
    """
    Hàm phụ trợ lấy chỉ số cảm biến gần nhất của một cây trồng.
    """
    readings = (
        db.collection("sensor_readings")
        .where("plantId", "==", plant_id)
        .order_by("timestamp", direction=FirestoreQuery.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in readings:
        data = doc.to_dict()
        ts_val = data.get("timestamp")
        ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)
        return {
            "reading_id": doc.id,
            "plant_id": plant_id,
            "sensor_id": data.get("sensorId", "sensor_01"),
            "timestamp": ts_str,
            "temperature": float(data.get("temperature", 0.0)),
            "soil_humidity": float(data.get("soilHumidity", 0.0)),
            "npk": data.get("npk", {"n": 0.0, "p": 0.0, "k": 0.0})
        }
    return None

def helper_get_unread_alerts_count(plant_id: str):
    """
    Hàm phụ trợ đếm số lượng cảnh báo chưa đọc của cây.
    """
    alerts = (
        db.collection("alerts")
        .where("plantId", "==", plant_id)
        .where("isRead", "==", False)
        .stream()
    )
    return len(list(alerts))

def helper_get_sensor_name(sensor_id: str) -> str:
    """
    Hàm lấy tên cảm biến hiển thị.
    """
    s_doc = db.collection("sensors").document(sensor_id).get()
    if s_doc.exists:
        return s_doc.to_dict().get("name", f"Cảm biến {sensor_id}")
    return f"Cảm biến {sensor_id}"

@router.get("", response_model=ResponseModel)
async def list_plants(
    user_id: str = Query(..., alias="userId", description="Mã người dùng (Firebase Auth UID)"),
    status_filter: str = Query("growing", alias="status", description="Lọc theo trạng thái: growing | harvested | all")
):
    """
    Lấy danh sách các kế hoạch trồng cây của người dùng (Phục vụ màn hình Dashboard Vườn Của Tôi):
    - Trả về thông tin cây kèm mã cảm biến (`sensor_id`) và chỉ số cảm biến mới nhất.
    """
    try:
        helper_ensure_default_sensors_exist()
        plants_stream = db.collection("plants").where("userId", "==", user_id).stream()
        results = []

        for doc in plants_stream:
            data = doc.to_dict()
            plant_status = data.get("status", "growing")
            if status_filter in ["growing", "harvested"] and plant_status != status_filter:
                continue

            planted_val = data.get("plantedAt")
            planted_str = planted_val.isoformat() if hasattr(planted_val, "isoformat") else str(planted_val)
            
            harvested_val = data.get("harvestedAt")
            harvested_str = (
                harvested_val.isoformat()
                if harvested_val and hasattr(harvested_val, "isoformat")
                else (str(harvested_val) if harvested_val else None)
            )

            plant_type = data.get("type", "cai_ngot")
            profile = PLANT_PROFILES.get(plant_type, {})
            type_label = profile.get("label", plant_type)
            sensor_id = data.get("sensorId", "sensor_01")
            sensor_name = helper_get_sensor_name(sensor_id)

            latest_sensor = helper_get_latest_sensor_reading(doc.id)
            unread_count = helper_get_unread_alerts_count(doc.id)

            results.append({
                "plant_id": doc.id,
                "user_id": data.get("userId", user_id),
                "name": data.get("name", "Chậu rau"),
                "type": plant_type,
                "type_label": type_label,
                "sensor_id": sensor_id,
                "sensor_name": sensor_name,
                "image_url": data.get("imageUrl"),
                "planted_at": planted_str,
                "placement": data.get("placement", "outdoor"),
                "status": data.get("status", "growing"),
                "harvested_at": harvested_str,
                "latest_sensor": latest_sensor,
                "unread_alert_count": unread_count
            })

        # Sắp xếp theo ngày trồng giảm dần
        results.sort(key=lambda x: x["planted_at"], reverse=True)

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} kế hoạch trồng cây."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi truy vấn danh sách cây trồng: {str(e)}"
        )

@router.get("/history", response_model=ResponseModel)
async def list_plant_history(
    user_id: str = Query(..., alias="userId", description="Mã người dùng")
):
    """
    Lấy lịch sử các kế hoạch trồng cây đã thu hoạch (`status: "harvested"`) cho màn hình Lịch Sử Trồng Cây.
    """
    return await list_plants(user_id=user_id, status_filter="harvested")

@router.get("/{plant_id}", response_model=ResponseModel)
async def get_plant_detail(plant_id: str):
    """
    Lấy thông tin chi tiết một kế hoạch trồng cây kèm theo cảm biến được gắn và thông số thời gian thực.
    """
    try:
        doc_ref = db.collection("plants").document(plant_id).get()
        if not doc_ref.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy kế hoạch trồng cây này."
            )

        data = doc_ref.to_dict()
        planted_val = data.get("plantedAt")
        planted_str = planted_val.isoformat() if hasattr(planted_val, "isoformat") else str(planted_val)

        harvested_val = data.get("harvestedAt")
        harvested_str = (
            harvested_val.isoformat()
            if harvested_val and hasattr(harvested_val, "isoformat")
            else (str(harvested_val) if harvested_val else None)
        )

        plant_type = data.get("type", "cai_ngot")
        profile = PLANT_PROFILES.get(plant_type, {})
        type_label = profile.get("label", plant_type)
        sensor_id = data.get("sensorId", "sensor_01")
        sensor_name = helper_get_sensor_name(sensor_id)

        latest_sensor = helper_get_latest_sensor_reading(plant_id)
        unread_count = helper_get_unread_alerts_count(plant_id)

        plant_data = {
            "plant_id": doc_ref.id,
            "user_id": data.get("userId"),
            "name": data.get("name"),
            "type": plant_type,
            "type_label": type_label,
            "sensor_id": sensor_id,
            "sensor_name": sensor_name,
            "image_url": data.get("imageUrl"),
            "planted_at": planted_str,
            "placement": data.get("placement", "outdoor"),
            "status": data.get("status", "growing"),
            "harvested_at": harvested_str,
            "latest_sensor": latest_sensor,
            "unread_alert_count": unread_count,
            "biological_profile": profile
        }

        return ResponseModel(success=True, data=plant_data)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy chi tiết cây trồng: {str(e)}"
        )

@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_plant(body: PlantCreateRequest):
    """
    Tạo một kế hoạch trồng cây mới (Thêm chậu cây mới):
    - Người dùng chọn 1 trong các cảm biến sẵn có (`sensor_01` hoặc `sensor_02`).
    - Hỗ trợ lưu đường dẫn/URL hình ảnh (`image_url`).
    """
    try:
        helper_ensure_default_sensors_exist()

        if body.type not in PLANT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại cây '{body.type}' không hợp lệ. Hợp lệ: {PLANT_TYPES}"
            )

        sensor_id = body.sensor_id or "sensor_01"
        sensor_doc_ref = db.collection("sensors").document(sensor_id)
        if not sensor_doc_ref.get().exists:
            # Tạo mới cảm biến nếu chưa có
            sensor_doc_ref.set({
                "sensorId": sensor_id,
                "name": f"Cảm biến {sensor_id}",
                "code": sensor_id.upper(),
                "status": "available",
                "currentPlantId": None,
                "createdAt": SERVER_TIMESTAMP
            })

        placement = body.placement if body.placement in PLACEMENTS else "outdoor"
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        plant_doc = {
            "userId": body.user_id,
            "name": body.name,
            "type": body.type,
            "sensorId": sensor_id,
            "imageUrl": body.image_url,
            "plantedAt": SERVER_TIMESTAMP,
            "placement": placement,
            "status": "growing",
            "harvestedAt": None
        }

        # Lưu cây mới vào Firestore
        new_doc_ref = db.collection("plants").document()
        new_doc_ref.set(plant_doc)

        # Gắn cảm biến cho cây mới này trong collection sensors
        sensor_doc_ref.update({
            "currentPlantId": new_doc_ref.id,
            "status": "assigned"
        })

        # Khởi tạo dữ liệu cảm biến ban đầu theo dải tối ưu của loại cây
        profile = PLANT_PROFILES[body.type]
        opt = profile["optimal"]

        initial_sensor = {
            "plantId": new_doc_ref.id,
            "sensorId": sensor_id,
            "timestamp": SERVER_TIMESTAMP,
            "temperature": round((opt["temp_min"] + opt["temp_max"]) / 2, 1),
            "soilHumidity": round((opt["soil_humidity_min"] + opt["soil_humidity_max"]) / 2, 1),
            "npk": {
                "n": round(opt["npk"]["n"], 1),
                "p": round(opt["npk"]["p"], 1),
                "k": round(opt["npk"]["k"], 1)
            }
        }
        db.collection("sensor_readings").add(initial_sensor)
        sensor_name = helper_get_sensor_name(sensor_id)

        return ResponseModel(
            success=True,
            data={
                "plant_id": new_doc_ref.id,
                "user_id": body.user_id,
                "name": body.name,
                "type": body.type,
                "type_label": profile["label"],
                "sensor_id": sensor_id,
                "sensor_name": sensor_name,
                "image_url": body.image_url,
                "planted_at": now_dt.isoformat(),
                "placement": placement,
                "status": "growing",
                "harvested_at": None
            },
            message=f"Tạo kế hoạch trồng cây mới thành công và đã gắn {sensor_name}!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thêm kế hoạch trồng cây mới: {str(e)}"
        )

@router.patch("/{plant_id}", response_model=ResponseModel)
async def update_plant(plant_id: str, body: PlantUpdateRequest):
    """
    Cập nhật thông tin kế hoạch trồng cây (Tên, cảm biến gắn, vị trí đặt, trạng thái):
    - Cho phép thay đổi cảm biến gắn cho cây (`sensor_id`).
    """
    try:
        doc_ref = db.collection("plants").document(plant_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy kế hoạch trồng cây để cập nhật."
            )

        update_fields = {}
        old_data = doc.to_dict()

        if body.name is not None:
            update_fields["name"] = body.name

        if body.sensor_id is not None and body.sensor_id != old_data.get("sensorId"):
            new_s_ref = db.collection("sensors").document(body.sensor_id)
            if new_s_ref.get().exists:
                update_fields["sensorId"] = body.sensor_id
                # Gán cảm biến mới cho cây này
                new_s_ref.update({"currentPlantId": plant_id, "status": "assigned"})

        if body.placement is not None:
            if body.placement not in PLACEMENTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vị trí đặt '{body.placement}' không hợp lệ. Hợp lệ: {PLACEMENTS}"
                )
            update_fields["placement"] = body.placement

        if body.status is not None:
            if body.status not in ["growing", "harvested"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Trạng thái không hợp lệ. Chỉ chấp nhận 'growing' hoặc 'harvested'."
                )
            update_fields["status"] = body.status
            if body.status == "harvested":
                update_fields["harvestedAt"] = SERVER_TIMESTAMP
                # Giải phóng cảm biến nếu thu hoạch
                curr_s_id = update_fields.get("sensorId", old_data.get("sensorId"))
                if curr_s_id:
                    s_ref = db.collection("sensors").document(curr_s_id)
                    if s_ref.get().exists:
                        s_ref.update({"currentPlantId": None, "status": "available"})

        if body.image_url is not None:
            update_fields["imageUrl"] = body.image_url

        if update_fields:
            doc_ref.update(update_fields)

        # Lấy lại document sau cập nhật
        updated_data = doc_ref.get().to_dict()
        planted_val = updated_data.get("plantedAt")
        planted_str = planted_val.isoformat() if hasattr(planted_val, "isoformat") else str(planted_val)

        harvested_val = updated_data.get("harvestedAt")
        harvested_str = (
            harvested_val.isoformat()
            if harvested_val and hasattr(harvested_val, "isoformat")
            else (str(harvested_val) if harvested_val else None)
        )

        plant_type = updated_data.get("type", "cai_ngot")
        profile = PLANT_PROFILES.get(plant_type, {})
        sensor_id = updated_data.get("sensorId", "sensor_01")
        sensor_name = helper_get_sensor_name(sensor_id)

        return ResponseModel(
            success=True,
            data={
                "plant_id": plant_id,
                "user_id": updated_data.get("userId"),
                "name": updated_data.get("name"),
                "type": plant_type,
                "type_label": profile.get("label", plant_type),
                "sensor_id": sensor_id,
                "sensor_name": sensor_name,
                "image_url": updated_data.get("imageUrl"),
                "planted_at": planted_str,
                "placement": updated_data.get("placement", "outdoor"),
                "status": updated_data.get("status", "growing"),
                "harvested_at": harvested_str
            },
            message="Cập nhật thông tin cây trồng thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật cây trồng: {str(e)}"
        )

@router.delete("/{plant_id}", response_model=ResponseModel)
async def delete_plant(plant_id: str):
    """
    Xóa kế hoạch trồng cây và toàn bộ dữ liệu liên quan (Cascade Delete):
    - Giải phóng cảm biến đã gắn với cây.
    - Xóa tất cả các chỉ số cảm biến trong `sensor_readings`.
    - Xóa tất cả các thông báo trong `alerts`.
    - Xóa tất cả các nhật ký trong `logs`.
    """
    try:
        plant_ref = db.collection("plants").document(plant_id)
        plant_doc = plant_ref.get()
        if not plant_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy cây trồng để xóa."
            )

        sensor_id = plant_doc.to_dict().get("sensorId")
        if sensor_id:
            s_ref = db.collection("sensors").document(sensor_id)
            if s_ref.get().exists:
                s_ref.update({"currentPlantId": None, "status": "available"})

        # Xóa liên hoàn các collections phụ thuộc
        collections_to_clean = ["sensor_readings", "alerts", "logs"]
        deleted_counts = {}

        for col_name in collections_to_clean:
            stream = db.collection(col_name).where("plantId", "==", plant_id).stream()
            batch = db.batch()
            count = 0
            for doc in stream:
                batch.delete(doc.reference)
                count += 1
                if count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
            if count % 400 != 0 and count > 0:
                batch.commit()
            deleted_counts[col_name] = count

        # Xóa cây chính
        plant_ref.delete()

        return ResponseModel(
            success=True,
            data={"plant_id": plant_id, "deleted_related_items": deleted_counts},
            message="Đã xóa thành công kế hoạch trồng cây và giải phóng thiết bị cảm biến."
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xóa cây trồng: {str(e)}"
        )
