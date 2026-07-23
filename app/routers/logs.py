from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import SERVER_TIMESTAMP, Query as FirestoreQuery
from app.config.firebase import db
from app.config.plant_constants import LOG_ACTIONS, PLANT_PROFILES
from app.models.schemas import ResponseModel, LogCreateRequest, LogResponse
import datetime
import random

router = APIRouter(prefix="/api/logs", tags=["Care Logs"])

@router.get("", response_model=ResponseModel)
async def list_care_logs(
    plant_id: str = Query(..., alias="plantId", description="Mã kế hoạch trồng cây"),
    limit: int = Query(50, ge=1, le=200, description="Số lượng nhật ký tối đa trả về")
):
    """
    Lấy danh sách các nhật ký chăm sóc cây (Tưới nước, Bón phân, Che mát, Đưa ra nắng...)
    Sắp xếp theo thời gian mới nhất lên đầu.
    """
    try:
        logs_stream = (
            db.collection("logs")
            .where("plantId", "==", plant_id)
            .order_by("timestamp", direction=FirestoreQuery.DESCENDING)
            .limit(limit)
            .stream()
        )

        results = []
        for doc in logs_stream:
            data = doc.to_dict()
            ts_val = data.get("timestamp")
            ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)

            results.append({
                "log_id": doc.id,
                "plant_id": data.get("plantId"),
                "action": data.get("action"),
                "notes": data.get("notes", ""),
                "timestamp": ts_str
            })

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} nhật ký chăm sóc."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy nhật ký chăm sóc: {str(e)}"
        )

@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_care_log(body: LogCreateRequest):
    """
    Thêm nhật ký chăm sóc cây mới (Phục vụ màn hình Thêm Nhật Ký Chăm Sóc):
    - Kiểm tra hành động hợp lệ (`watering`, `fertilizing`, `shade_covering`, `sun_exposure`, `pest_control`, `harvesting`).
    - Tự động thực thi các tác dụng phụ (Side Effects) lên thông tin cây:
      + `shade_covering`: Đổi vị trí cây thành `shaded` (che mát).
      + `sun_exposure`: Đổi vị trí cây thành `outdoor` (đưa ra nắng).
      + `harvesting`: Đổi trạng thái cây thành `harvested` và cập nhật ngày thu hoạch.
    """
    try:
        if body.action not in LOG_ACTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hành động '{body.action}' không hợp lệ. Hợp lệ: {LOG_ACTIONS}"
            )

        plant_ref = db.collection("plants").document(body.plant_id)
        plant_doc = plant_ref.get()
        if not plant_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy kế hoạch trồng cây để thêm nhật ký."
            )

        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # Lưu nhật ký mới
        log_data = {
            "plantId": body.plant_id,
            "action": body.action,
            "notes": body.notes or "",
            "timestamp": SERVER_TIMESTAMP
        }
        new_log_ref = db.collection("logs").document()
        new_log_ref.set(log_data)

        # Xử lý các Tác dụng phụ (Side Effects) và CẬP NHẬT NGAY THÔNG SỐ CẢM BIẾN vào Firestore
        side_effects_applied = []
        plant_info = plant_doc.to_dict()
        plant_type = plant_info.get("type", "cai_ngot")
        profile = PLANT_PROFILES.get(plant_type, PLANT_PROFILES["cai_ngot"])

        # Lấy thông số cảm biến gần nhất làm cơ sở
        readings_stream = (
            db.collection("sensor_readings")
            .where("plantId", "==", body.plant_id)
            .order_by("timestamp", direction=FirestoreQuery.DESCENDING)
            .limit(1)
            .stream()
        )
        last_sensor = None
        for doc in readings_stream:
            last_sensor = doc.to_dict()
            break

        opt = profile["optimal"]
        current_temp = float(last_sensor.get("temperature", 28.0)) if last_sensor else float((opt["temp_min"] + opt["temp_max"]) / 2)
        current_soil_humidity = float(last_sensor.get("soilHumidity", 70.0)) if last_sensor else float((opt["soil_humidity_min"] + opt["soil_humidity_max"]) / 2)
        current_npk = dict(last_sensor.get("npk", opt["npk"])) if last_sensor else dict(opt["npk"])

        new_sensor_needed = False

        if body.action == "watering":
            current_soil_humidity = round(random.uniform(85.0, 90.0), 1)
            current_temp = round(max(15.0, current_temp - 2.5), 1)
            new_sensor_needed = True
            side_effects_applied.append("Đã cập nhật ngay: Độ ẩm đất tăng lên 85-90% và nhiệt độ hạ 2.5°C!")

        elif body.action == "fertilizing":
            boost = profile["npk_fertilizer_boost"]
            npk_max = profile["npk_max"]
            current_npk["n"] = round(min(npk_max["n"], current_npk.get("n", 0.0) + boost["n"]), 1)
            current_npk["p"] = round(min(npk_max["p"], current_npk.get("p", 0.0) + boost["p"]), 1)
            current_npk["k"] = round(min(npk_max["k"], current_npk.get("k", 0.0) + boost["k"]), 1)
            new_sensor_needed = True
            side_effects_applied.append(f"Đã cộng ngay dinh dưỡng NPK vào đất (N: {current_npk['n']}, P: {current_npk['p']}, K: {current_npk['k']} mg/kg)!")

        elif body.action == "shade_covering":
            plant_ref.update({"placement": "shaded"})
            current_temp = round(max(20.0, current_temp - 3.0), 1)
            new_sensor_needed = True
            side_effects_applied.append("Đã chuyển vị trí cây thành 'shaded' và làm dịu nhiệt độ môi trường!")

        elif body.action == "sun_exposure":
            plant_ref.update({"placement": "outdoor"})
            current_temp = round(min(40.0, current_temp + 2.0), 1)
            new_sensor_needed = True
            side_effects_applied.append("Đã chuyển vị trí cây thành 'outdoor'!")

        elif body.action == "harvesting":
            plant_ref.update({
                "status": "harvested",
                "harvestedAt": SERVER_TIMESTAMP
            })
            side_effects_applied.append("Đã chuyển trạng thái cây sang đã thu hoạch ('harvested').")

        # Ghi ngay lập tức bản ghi cảm biến mới vào Firestore
        if new_sensor_needed:
            sensor_id = plant_info.get("sensorId", "sensor_01")
            new_sensor_doc = {
                "plantId": body.plant_id,
                "sensorId": sensor_id,
                "timestamp": SERVER_TIMESTAMP,
                "temperature": current_temp,
                "soilHumidity": current_soil_humidity,
                "npk": current_npk
            }
            db.collection("sensor_readings").add(new_sensor_doc)

        return ResponseModel(
            success=True,
            data={
                "log_id": new_log_ref.id,
                "plant_id": body.plant_id,
                "action": body.action,
                "notes": body.notes or "",
                "timestamp": now_dt.isoformat(),
                "side_effects": side_effects_applied,
                "updated_sensor": {
                    "temperature": current_temp,
                    "soil_humidity": current_soil_humidity,
                    "npk": current_npk
                } if new_sensor_needed else None
            },
            message="Thêm nhật ký chăm sóc và cập nhật thông số cây thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thêm nhật ký chăm sóc: {str(e)}"
        )
