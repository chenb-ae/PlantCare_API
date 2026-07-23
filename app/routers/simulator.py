from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import SERVER_TIMESTAMP, Query as FirestoreQuery
from app.config.firebase import db
from app.config.plant_constants import PLANT_PROFILES
from app.models.schemas import ResponseModel
from app.routers.sensors import helper_ensure_default_sensors_exist
import math
import random
import datetime

router = APIRouter(prefix="/api/simulator", tags=["Sensor Simulator Engine"])

def helper_run_simulation_for_sensor(sensor_doc_id: str, sensor_data: dict) -> dict:
    """
    Thực thi 1 bước giả lập 15 phút biến động tự nhiên độc lập cho THIẾT BỊ CẢM BIẾN (`sensor_id`):
    - Đọc bản ghi cảm biến MỚI NHẤT làm điểm xuất phát.
    - Áp dụng suy hao tự nhiên (đất khô dần theo thời gian, cây hấp thụ bớt NPK) và chu kỳ nhiệt độ ngày/đêm.
    - KHÔNG can thiệp hay đọc lại nhật ký cũ (vì khi người dùng tưới nước/bón phân, API /api/logs đã lập tức cộng số liệu vào Firestore).
    """
    sensor_id = sensor_data.get("sensorId", sensor_doc_id)
    temp_offset = float(sensor_data.get("tempOffset", 0.0))
    humidity_offset = float(sensor_data.get("humidityOffset", 0.0))
    plant_id = sensor_data.get("currentPlantId")

    plant_data = None
    plant_name = None
    plant_type = "cai_ngot"
    placement = "outdoor"

    if plant_id:
        p_doc = db.collection("plants").document(plant_id).get()
        if p_doc.exists:
            plant_data = p_doc.to_dict()
            if plant_data.get("status") == "growing":
                plant_name = plant_data.get("name")
                plant_type = plant_data.get("type", "cai_ngot")
                placement = plant_data.get("placement", "outdoor")
            else:
                plant_id = None  # Cây đã thu hoạch

    profile = PLANT_PROFILES.get(plant_type, PLANT_PROFILES["cai_ngot"])
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    current_hour = now_dt.hour + now_dt.minute / 60.0

    # 1. Giả lập Nhiệt độ môi trường (°C) theo chu kỳ thời gian trong ngày
    noise_temp = random.uniform(-0.4, 0.4)
    if placement == "shaded":
        # Trong bóng râm / Trong nhà: Nhiệt độ dịu hơn (26°C ± 2°C)
        temp = 26.0 + 2.0 * math.sin(2 * math.pi * (current_hour - 8) / 24.0) + noise_temp + temp_offset
    else:
        # Ngoài trời phơi nắng: Nhiệt độ nền dao động mạnh hơn (29°C ± 4°C)
        temp = 29.0 + 4.0 * math.sin(2 * math.pi * (current_hour - 8) / 24.0) + noise_temp + temp_offset

    temp = round(max(10.0, min(50.0, temp)), 1)

    # 2. Lấy chỉ số cảm biến lần cuối của thiết bị này trong Firestore
    last_reading = None
    readings_stream = (
        db.collection("sensor_readings")
        .where("sensorId", "==", sensor_id)
        .order_by("timestamp", direction=FirestoreQuery.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in readings_stream:
        last_reading = doc.to_dict()
        break

    if not last_reading:
        # Nếu chưa từng có chỉ số, xuất phát từ dải tối ưu của loại cây
        opt = profile["optimal"]
        prev_soil_humidity = (opt["soil_humidity_min"] + opt["soil_humidity_max"]) / 2.0 + humidity_offset
        prev_npk = dict(opt["npk"])
    else:
        prev_soil_humidity = float(last_reading.get("soilHumidity", 70.0))
        prev_npk = dict(last_reading.get("npk", profile["optimal"]["npk"]))

    # 3. Giả lập Độ ẩm đất (%) suy hao tự nhiên theo thời gian
    decay_rate = 0.8 if temp >= 30.0 else 0.3
    noise_soil = random.uniform(-0.1, 0.1)
    soil_humidity = round(max(15.0, min(98.0, prev_soil_humidity - decay_rate + noise_soil)), 1)

    # 4. Giả lập Lượng NPK (mg/kg) tiêu thụ tự nhiên theo thời gian
    npk_decay = profile["npk_decay_per_15min"]
    new_n = max(0.0, prev_npk.get("n", profile["optimal"]["npk"]["n"]) - npk_decay["n"] + random.uniform(-0.05, 0.05))
    new_p = max(0.0, prev_npk.get("p", profile["optimal"]["npk"]["p"]) - npk_decay["p"] + random.uniform(-0.02, 0.02))
    new_k = max(0.0, prev_npk.get("k", profile["optimal"]["npk"]["k"]) - npk_decay["k"] + random.uniform(-0.04, 0.04))

    new_npk = {
        "n": round(new_n, 1),
        "p": round(new_p, 1),
        "k": round(new_k, 1)
    }

    # 5. Lưu bản ghi sensor_readings mới vào Firestore
    new_sensor_doc = {
        "sensorId": sensor_id,
        "plantId": plant_id,
        "timestamp": SERVER_TIMESTAMP,
        "temperature": temp,
        "soilHumidity": soil_humidity,
        "npk": new_npk
    }
    db.collection("sensor_readings").add(new_sensor_doc)

    # 6. Kiểm tra Cảnh báo nếu cảm biến đang gắn với chậu cây đang trồng
    alerts_created = []
    if plant_id:
        tolerable = profile["tolerable"]

        if temp > tolerable["temp_max"]:
            alerts_created.append({
                "type": "HIGH_TEMP",
                "message": f"[{sensor_data.get('name', sensor_id)}] Nhiệt độ hiện tại ({temp}°C) vượt quá ngưỡng chịu đựng của {profile['label']} ({tolerable['temp_max']}°C). Bạn nên che mát hoặc di chuyển cây!"
            })
        elif temp < tolerable["temp_min"]:
            alerts_created.append({
                "type": "LOW_TEMP",
                "message": f"[{sensor_data.get('name', sensor_id)}] Nhiệt độ hiện tại ({temp}°C) thấp hơn ngưỡng chịu đựng của {profile['label']} ({tolerable['temp_min']}°C)."
            })

        if soil_humidity < tolerable["soil_humidity_min"]:
            alerts_created.append({
                "type": "LOW_SOIL_MOISTURE",
                "message": f"[{sensor_data.get('name', sensor_id)}] Độ ẩm đất ({soil_humidity}%) đang bị khô dưới ngưỡng chịu đựng ({tolerable['soil_humidity_min']}%). Vui lòng tưới nước!"
            })
        elif soil_humidity > tolerable["soil_humidity_max"]:
            alerts_created.append({
                "type": "HIGH_SOIL_MOISTURE",
                "message": f"[{sensor_data.get('name', sensor_id)}] Độ ẩm đất ({soil_humidity}%) quá cao dẫn tới ngập úng rễ."
            })

        npk_tol = tolerable["npk"]
        if new_npk["n"] < npk_tol["n_min"] or new_npk["p"] < npk_tol["p_min"] or new_npk["k"] < npk_tol["k_min"]:
            alerts_created.append({
                "type": "LOW_NPK",
                "message": f"[{sensor_data.get('name', sensor_id)}] Hàm lượng dinh dưỡng NPK ({new_npk['n']}/{new_npk['p']}/{new_npk['k']} mg/kg) bị thiếu hụt. Bạn nên bón thêm phân!"
            })

        # Lưu cảnh báo vào Firestore (tránh trùng lặp trong vòng 1 giờ)
        for alert_item in alerts_created:
            one_hour_ago = now_dt - datetime.timedelta(hours=1)
            recent_alerts = (
                db.collection("alerts")
                .where("plantId", "==", plant_id)
                .where("type", "==", alert_item["type"])
                .where("timestamp", ">=", one_hour_ago)
                .limit(1)
                .stream()
            )
            if len(list(recent_alerts)) == 0:
                alert_doc = {
                    "plantId": plant_id,
                    "sensorId": sensor_id,
                    "type": alert_item["type"],
                    "message": alert_item["message"],
                    "timestamp": SERVER_TIMESTAMP,
                    "isRead": False
                }
                db.collection("alerts").add(alert_doc)

    return {
        "sensor_id": sensor_id,
        "sensor_name": sensor_data.get("name"),
        "bound_plant_id": plant_id,
        "bound_plant_name": plant_name,
        "temperature": temp,
        "soil_humidity": soil_humidity,
        "npk": new_npk,
        "alerts_generated_count": len(alerts_created)
    }

@router.post("/run", response_model=ResponseModel)
async def run_simulator_cron():
    """
    API Kích hoạt chu kỳ giả lập suy hao tự nhiên (Google Cloud Scheduler gọi định kỳ 15 phút một lần):
    - Đọc điểm dữ liệu cảm biến mới nhất và áp dụng tốc độ suy hao môi trường tự nhiên.
    - KHÔNG kiểm tra nhật ký cũ để tránh trùng lặp.
    """
    try:
        helper_ensure_default_sensors_exist()
        sensors_stream = db.collection("sensors").stream()
        results = []
        total_alerts = 0

        for doc in sensors_stream:
            s_data = doc.to_dict()
            res = helper_run_simulation_for_sensor(doc.id, s_data)
            results.append(res)
            total_alerts += res["alerts_generated_count"]

        return ResponseModel(
            success=True,
            data={
                "processed_sensors_count": len(results),
                "total_alerts_generated": total_alerts,
                "details": results
            },
            message=f"Đã giả lập thành công suy hao tự nhiên cho {len(results)} thiết bị cảm biến!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thực thi bộ giả lập cảm biến: {str(e)}"
        )

@router.post("/trigger-sensor/{sensor_id}", response_model=ResponseModel)
async def trigger_simulator_for_single_sensor(sensor_id: str):
    """
    API Kích hoạt thủ công 1 bước giả lập cho MỘT THIẾT BỊ CẢM BIẾN cụ thể.
    """
    try:
        sensor_ref = db.collection("sensors").document(sensor_id)
        s_doc = sensor_ref.get()
        if not s_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy thiết bị cảm biến '{sensor_id}'."
            )

        res = helper_run_simulation_for_sensor(sensor_id, s_doc.to_dict())

        return ResponseModel(
            success=True,
            data=res,
            message=f"Kích hoạt giả lập dữ liệu thành công cho cảm biến '{sensor_id}'!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi giả lập cảm biến: {str(e)}"
        )
