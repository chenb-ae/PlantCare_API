from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import SERVER_TIMESTAMP, Query as FirestoreQuery
from app.config.firebase import db
from app.config.plant_constants import PLANT_PROFILES
from app.models.schemas import ResponseModel, AlertResponse, UnreadCountResponse
from firebase_admin import auth as firebase_auth, messaging
import datetime

router = APIRouter(prefix="/api/alerts", tags=["Smart Alerts & Notifications"])

def send_fcm_notification_to_user(user_id: str, title: str, body: str, plant_id: str = None):
    """
    Gửi thông báo đẩy Firebase Cloud Messaging (FCM) trực tiếp tới điện thoại người dùng (Kể cả khi APP ĐÃ ĐÓNG TẮT HOÀN TOÀN).
    """
    try:
        u_doc = db.collection("users").document(user_id).get()
        if not u_doc.exists:
            return
        fcm_token = u_doc.to_dict().get("fcmToken")
        if not fcm_token:
            return

        msg = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                "plantId": plant_id or "",
                "click_action": "FLUTTER_NOTIFICATION_CLICK"
            },
            token=fcm_token,
        )
        resp = messaging.send(msg)
        print(f"[FCM] Đã nổ thông báo đẩy thành công: {resp}")
    except Exception as e:
        print(f"[FCM] Lỗi gửi thông báo: {e}")

def evaluate_live_plant_alerts(plant_id: str, force: bool = False):
    """
    Đánh giá chỉ số cảm biến mới nhất của chậu cây với dải chịu đựng sinh học và tự động tạo bản ghi cảnh báo.
    """
    try:
        p_doc = db.collection("plants").document(plant_id).get()
        if not p_doc.exists:
            return []
        p_data = p_doc.to_dict()
        if p_data.get("status") != "growing":
            return []

        plant_name = p_data.get("name", "Chậu cây")
        plant_type = p_data.get("type", "cai_ngot")
        sensor_id = p_data.get("sensorId", "sensor_01")
        profile = PLANT_PROFILES.get(plant_type, PLANT_PROFILES["cai_ngot"])
        plant_label = profile["label"]
        tolerable = profile["tolerable"]

        # Lấy chỉ số mới nhất (lọc và sắp xếp bộ nhớ)
        def get_ts(x):
            ts = x.get("timestamp")
            if hasattr(ts, "timestamp"):
                return ts.timestamp()
            return str(ts or "")

        readings_stream = db.collection("sensor_readings").where("plantId", "==", plant_id).stream()
        readings_list = [d.to_dict() for d in readings_stream]
        if not readings_list:
            readings_stream = db.collection("sensor_readings").where("sensorId", "==", sensor_id).stream()
            readings_list = [d.to_dict() for d in readings_stream]

        if not readings_list:
            return []

        readings_list.sort(key=get_ts, reverse=True)
        latest_data = readings_list[0]
        temp = float(latest_data.get("temperature", 28.0))
        soil_humidity = float(latest_data.get("soilHumidity", 70.0))
        npk = latest_data.get("npk", {"n": 50.0, "p": 30.0, "k": 40.0})

        alerts_created = []

        if temp > tolerable["temp_max"]:
            alerts_created.append({
                "type": "HIGH_TEMP",
                "message": f"[{plant_name} - {plant_label}] Nhiệt độ ({temp}°C) vượt quá ngưỡng chịu đựng ({tolerable['temp_max']}°C). Bạn nên che mát hoặc di chuyển cây vào trong nhà!"
            })
        elif temp < tolerable["temp_min"]:
            alerts_created.append({
                "type": "LOW_TEMP",
                "message": f"[{plant_name} - {plant_label}] Nhiệt độ ({temp}°C) thấp hơn ngưỡng chịu đựng ({tolerable['temp_min']}°C)."
            })

        if soil_humidity < tolerable["soil_humidity_min"]:
            alerts_created.append({
                "type": "LOW_SOIL_MOISTURE",
                "message": f"[{plant_name} - {plant_label}] Độ ẩm đất ({soil_humidity}%) quá khô dưới ngưỡng ({tolerable['soil_humidity_min']}%). Vui lòng tưới nước!"
            })
        elif soil_humidity > tolerable["soil_humidity_max"]:
            alerts_created.append({
                "type": "HIGH_SOIL_MOISTURE",
                "message": f"[{plant_name} - {plant_label}] Độ ẩm đất ({soil_humidity}%) vượt quá ngưỡng tối đa ({tolerable['soil_humidity_max']}%). Đất đang bị ngập úng rễ!"
            })

        npk_tol = tolerable["npk"]
        n_val = float(npk.get("n", 0))
        p_val = float(npk.get("p", 0))
        k_val = float(npk.get("k", 0))

        if n_val < npk_tol["n_min"] or p_val < npk_tol["p_min"] or k_val < npk_tol["k_min"]:
            alerts_created.append({
                "type": "LOW_NPK",
                "message": f"[{plant_name} - {plant_label}] Dinh dưỡng NPK ({n_val}/{p_val}/{k_val} mg/kg) bị thiếu hụt so với ngưỡng (Min N:{npk_tol['n_min']}, P:{npk_tol['p_min']}, K:{npk_tol['k_min']}). Bạn nên bón thêm phân!"
            })

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        one_hour_ago = now_dt - datetime.timedelta(hours=1)

        saved = []
        for alert_item in alerts_created:
            has_recent = False
            if not force:
                alerts_stream = db.collection("alerts").where("plantId", "==", plant_id).stream()
                for a_doc in alerts_stream:
                    a_data = a_doc.to_dict()
                    if a_data.get("type") == alert_item["type"]:
                        ts = a_data.get("timestamp")
                        if isinstance(ts, datetime.datetime) and ts >= one_hour_ago:
                            has_recent = True
                            break
            if not has_recent or force:
                alert_doc = {
                    "plantId": plant_id,
                    "sensorId": sensor_id,
                    "type": alert_item["type"],
                    "message": alert_item["message"],
                    "timestamp": SERVER_TIMESTAMP,
                    "isRead": False
                }
                _, ref = db.collection("alerts").add(alert_doc)
                saved.append(ref.id)

        return saved
    except Exception as e:
        print(f"Lỗi evaluate_live_plant_alerts: {e}")
        return []

@router.get("", response_model=ResponseModel)
async def list_alerts(
    user_id: str = Query(..., alias="userId", description="Mã người dùng"),
    plant_id: str = Query(None, alias="plantId", description="Lọc cảnh báo theo mã cây cụ thể"),
    unread_only: bool = Query(False, alias="unreadOnly", description="Chỉ lấy các cảnh báo chưa đọc")
):
    """
    Lấy danh sách thông báo cảnh báo vượt ngưỡng của người dùng (Màn hình Thông báo cảnh báo):
    - Đính kèm tên cây (`plant_name`) và `plant_id` để khi người dùng nhấn vào thông báo, ứng dụng Flutter sẽ điều hướng trực tiếp tới chậu cây tương ứng.
    """
    try:
        # 1. Lấy danh sách cây thuộc về user
        user_plants_stream = db.collection("plants").where("userId", "==", user_id).stream()
        user_plant_map = {}
        for p_doc in user_plants_stream:
            p_data = p_doc.to_dict()
            if p_data.get("status") == "growing":
                user_plant_map[p_doc.id] = p_data.get("name", "Chậu cây")

        if not user_plant_map:
            return ResponseModel(success=True, data=[], message="Người dùng chưa có cây trồng nào.")

        target_plant_ids = [plant_id] if plant_id else list(user_plant_map.keys())

        # Firestore limit 'in' query to 30 items
        results = []
        for i in range(0, len(target_plant_ids), 30):
            batch_ids = target_plant_ids[i:i+30]
            query = db.collection("alerts").where("plantId", "in", batch_ids)
            alerts_stream = query.stream()

            for doc in alerts_stream:
                a_data = doc.to_dict()
                is_read = bool(a_data.get("isRead", False))
                if unread_only and is_read:
                    continue

                ts_val = a_data.get("timestamp")
                ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)
                p_id = a_data.get("plantId")

                results.append({
                    "alert_id": doc.id,
                    "plant_id": p_id,
                    "plant_name": user_plant_map.get(p_id, "Chậu cây"),
                    "type": a_data.get("type", "LOW_SOIL_MOISTURE"),
                    "message": a_data.get("message", ""),
                    "timestamp": ts_str,
                    "is_read": bool(a_data.get("isRead", False))
                })

        # Sắp xếp lại danh sách kết quả theo thời gian mới nhất
        results.sort(key=lambda x: x["timestamp"], reverse=True)

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} thông báo cảnh báo."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách cảnh báo: {str(e)}"
        )

@router.post("/trigger-test-warning", response_model=ResponseModel)
async def trigger_test_warning(
    user_id: str = Query(..., alias="userId", description="Mã người dùng")
):
    """
    Tạo một thông báo cảnh báo thử nghiệm vượt ngưỡng sinh học cho người dùng.
    """
    try:
        user_plants_stream = db.collection("plants").where("userId", "==", user_id).where("status", "==", "growing").stream()
        plants = list(user_plants_stream)
        if not plants:
            plant_id = "demo_plant"
            plant_name = "Chậu Cải Thìa Thử Nghiệm"
        else:
            p_doc = plants[0]
            plant_id = p_doc.id
            plant_name = p_doc.to_dict().get("name", "Chậu cây")

        alert_doc = {
            "plantId": plant_id,
            "sensorId": "sensor_01",
            "type": "HIGH_SOIL_MOISTURE",
            "message": f"[{plant_name} - Cải thìa] Độ ẩm đất (86%) vượt quá ngưỡng tối đa (85%). Đất đang bị ngập úng rễ!",
            "timestamp": SERVER_TIMESTAMP,
            "isRead": False
        }
        _, ref = db.collection("alerts").add(alert_doc)

        return ResponseModel(
            success=True,
            data={"alert_id": ref.id, "plant_id": plant_id},
            message="Đã tạo thông báo cảnh báo thử nghiệm thành công!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo cảnh báo thử nghiệm: {str(e)}"
        )

@router.get("/unread-count", response_model=ResponseModel)
async def get_unread_count(
    user_id: str = Query(..., alias="userId", description="Mã người dùng")
):
    """
    Đếm số lượng cảnh báo chưa đọc của người dùng.
    """
    try:
        user_plants_stream = db.collection("plants").where("userId", "==", user_id).stream()
        user_plant_ids = [p_doc.id for p_doc in user_plants_stream]

        if not user_plant_ids:
            return ResponseModel(success=True, data={"user_id": user_id, "unread_count": 0})

        unread_count = 0
        for i in range(0, len(user_plant_ids), 30):
            batch_ids = user_plant_ids[i:i+30]
            alerts = db.collection("alerts").where("plantId", "in", batch_ids).stream()
            for a_doc in alerts:
                if a_doc.to_dict().get("isRead") is False:
                    unread_count += 1

        return ResponseModel(
            success=True,
            data={
                "user_id": user_id,
                "unread_count": unread_count
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đếm cảnh báo chưa đọc: {str(e)}"
        )

@router.patch("/{alert_id}/read", response_model=ResponseModel)
async def mark_alert_as_read(alert_id: str):
    """
    Đánh dấu một thông báo cảnh báo là đã đọc (`isRead: True`).
    """
    try:
        doc_ref = db.collection("alerts").document(alert_id)
        if not doc_ref.get().exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông báo cảnh báo."
            )

        doc_ref.update({"isRead": True})

        return ResponseModel(
            success=True,
            data={"alert_id": alert_id, "is_read": True},
            message="Đã đánh dấu thông báo là đã đọc."
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đánh dấu thông báo đã đọc: {str(e)}"
        )

@router.patch("/read-all", response_model=ResponseModel)
async def mark_all_alerts_as_read(
    user_id: str = Query(..., alias="userId", description="Mã người dùng")
):
    """
    Đánh dấu tất cả thông báo cảnh báo của người dùng là đã đọc.
    """
    try:
        user_plants_stream = db.collection("plants").where("userId", "==", user_id).stream()
        user_plant_ids = [p_doc.id for p_doc in user_plants_stream]

        if not user_plant_ids:
            return ResponseModel(success=True, data={"updated_count": 0}, message="Không có cảnh báo nào.")

        updated_count = 0
        for i in range(0, len(user_plant_ids), 30):
            batch_ids = user_plant_ids[i:i+30]
            alerts_stream = (
                db.collection("alerts")
                .where("plantId", "in", batch_ids)
                .where("isRead", "==", False)
                .stream()
            )
            
            batch = db.batch()
            count = 0
            for doc in alerts_stream:
                batch.update(doc.reference, {"isRead": True})
                count += 1
                if count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
            if count % 400 != 0 and count > 0:
                batch.commit()
            updated_count += count

        return ResponseModel(
            success=True,
            data={"user_id": user_id, "updated_count": updated_count},
            message=f"Đã đánh dấu tất cả {updated_count} thông báo là đã đọc."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đánh dấu tất cả đã đọc: {str(e)}"
        )
