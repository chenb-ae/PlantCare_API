from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from google.cloud.firestore import SERVER_TIMESTAMP, Query as FirestoreQuery
from app.config.firebase import db
from app.config.plant_constants import PLANT_PROFILES
from app.models.schemas import ResponseModel
from app.routers.sensors import helper_ensure_default_sensors_exist
from pydantic import BaseModel, Field
from typing import Optional
import math
import random
import datetime

router = APIRouter(tags=["Sensor Simulator Engine"])

class OverrideSensorRequest(BaseModel):
    sensor_id: str = Field(..., example="sensor_01")
    temperature: Optional[float] = Field(None, example=38.5)
    soil_humidity: Optional[float] = Field(None, example=40.0)
    n: Optional[float] = Field(None, example=15.0)
    p: Optional[float] = Field(None, example=10.0)
    k: Optional[float] = Field(None, example=12.0)

def helper_run_simulation_for_sensor(sensor_doc_id: str, sensor_data: dict) -> dict:
    """
    Thực thi 1 bước giả lập 15 phút biến động tự nhiên độc lập cho THIẾT BỊ CẢM BIẾN (`sensor_id`).
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
                plant_id = None

    profile = PLANT_PROFILES.get(plant_type, PLANT_PROFILES["cai_ngot"])
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    now_dt = datetime.datetime.now(vn_tz)
    current_hour = now_dt.hour + now_dt.minute / 60.0

    # 1. Giả lập Nhiệt độ môi trường (°C) theo chu kỳ thời gian trong ngày theo múi giờ Việt Nam
    noise_temp = random.uniform(-0.4, 0.4)
    if placement == "shaded":
        temp = 26.0 + 2.0 * math.sin(2 * math.pi * (current_hour - 8) / 24.0) + noise_temp + temp_offset
    else:
        temp = 29.0 + 4.0 * math.sin(2 * math.pi * (current_hour - 8) / 24.0) + noise_temp + temp_offset

    temp = round(max(10.0, min(50.0, temp)), 1)

    # 2. Lấy chỉ số cảm biến lần cuối của thiết bị này trong Firestore (lọc & sắp xếp bộ nhớ)
    readings_stream = db.collection("sensor_readings").where("sensorId", "==", sensor_id).stream()
    readings = []
    for doc in readings_stream:
        readings.append(doc.to_dict())

    def get_ts(x):
        ts = x.get("timestamp")
        if hasattr(ts, "timestamp"):
            return ts.timestamp()
        return str(ts or "")

    readings.sort(key=get_ts, reverse=True)
    last_reading = readings[0] if readings else None

    if not last_reading:
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

    # 6. Kiểm tra Cảnh báo
    alerts_created = []
    if plant_id:
        from app.routers.alerts import evaluate_live_plant_alerts
        alerts_created = evaluate_live_plant_alerts(plant_id)

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

@router.get("/api/simulator/run", response_model=ResponseModel)
@router.post("/api/simulator/run", response_model=ResponseModel)
async def run_simulator_cron():
    """
    API Kích hoạt chu kỳ giả lập suy hao tự nhiên (Vercel Cron Job gọi định kỳ mỗi 15 phút một lần):
    - Tương thích 100% với Vercel Cron (tự động gửi GET/POST request mỗi 15 phút).
    """
    try:
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

@router.post("/api/simulator/trigger-sensor/{sensor_id}", response_model=ResponseModel)
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

@router.post("/api/simulator/override", response_model=ResponseModel)
async def override_sensor_values(body: OverrideSensorRequest):
    """
    API Bảng điều khiển Demo (Phục vụ Báo cáo Đồ án / Demo Giảng viên):
    - Áp đặt trực tiếp thông số Nhiệt độ, Độ ẩm, NPK cho MỘT CẢM BIẾN CỤ THỂ (`sensor_id`).
    - Sau khi cảm biến cập nhật chỉ số, chậu cây đang kết nối với cảm biến đó sẽ nhận chỉ số mới và phát sinh cảnh báo.
    """
    try:
        s_ref = db.collection("sensors").document(body.sensor_id)
        s_doc = s_ref.get()
        if not s_doc.exists:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy thiết bị cảm biến '{body.sensor_id}'.")

        s_data = s_doc.to_dict()
        plant_id = s_data.get("currentPlantId")
        user_id = None
        plant_name = None

        if plant_id:
            p_doc = db.collection("plants").document(plant_id).get()
            if p_doc.exists:
                p_dict = p_doc.to_dict()
                user_id = p_dict.get("userId")
                plant_name = p_dict.get("name")

        # Lấy bản ghi cảm biến mới nhất của thiết bị này
        readings_stream = db.collection("sensor_readings").where("sensorId", "==", body.sensor_id).stream()
        readings = [d.to_dict() for d in readings_stream]
        def get_ts(x):
            ts = x.get("timestamp")
            if hasattr(ts, "timestamp"): return ts.timestamp()
            return str(ts or "")
        readings.sort(key=get_ts, reverse=True)
        last_reading = readings[0] if readings else {}

        new_temp = body.temperature if body.temperature is not None else float(last_reading.get("temperature", 28.0))
        new_humidity = body.soil_humidity if body.soil_humidity is not None else float(last_reading.get("soilHumidity", 75.0))

        last_npk = last_reading.get("npk", {"n": 50.0, "p": 30.0, "k": 40.0})
        new_n = body.n if body.n is not None else float(last_npk.get("n", 50.0))
        new_p = body.p if body.p is not None else float(last_npk.get("p", 30.0))
        new_k = body.k if body.k is not None else float(last_npk.get("k", 40.0))

        new_sensor_doc = {
            "sensorId": body.sensor_id,
            "plantId": plant_id,
            "timestamp": SERVER_TIMESTAMP,
            "temperature": new_temp,
            "soilHumidity": new_humidity,
            "npk": {"n": new_n, "p": new_p, "k": new_k}
        }
        db.collection("sensor_readings").add(new_sensor_doc)

        created_alerts = []
        if plant_id:
            from app.routers.alerts import evaluate_live_plant_alerts, send_fcm_notification_to_user
            created_alerts = evaluate_live_plant_alerts(plant_id, force=True)

            if user_id and created_alerts:
                send_fcm_notification_to_user(
                    user_id=user_id,
                    title=f"⚠️ Cảnh báo Demo: {plant_name or 'Chậu cây'}",
                    body=f"Cảm biến {body.sensor_id} vừa thay đổi: Nhiệt độ {new_temp}°C, Độ ẩm {new_humidity}%, NPK ({new_n}/{new_p}/{new_k}).",
                    plant_id=plant_id
                )

        return ResponseModel(
            success=True,
            data={
                "sensor_id": body.sensor_id,
                "bound_plant_id": plant_id,
                "bound_plant_name": plant_name,
                "temperature": new_temp,
                "soil_humidity": new_humidity,
                "npk": {"n": new_n, "p": new_p, "k": new_k},
                "generated_alerts_count": len(created_alerts)
            },
            message=f"Đã can thiệp chỉ số cho Cảm biến '{body.sensor_id}' thành công! Trực thuộc chậu: '{plant_name or 'Chưa gắn'}' (Tạo {len(created_alerts)} cảnh báo)."
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi can thiệp Cảm biến Demo: {str(e)}")

@router.get("/demo", response_class=HTMLResponse)
async def get_demo_control_panel():
    """
    Giao diện Bảng điều khiển Demo Giảng viên (Phục vụ Báo cáo & Bảo vệ Đồ án):
    - Truy cập trực tiếp tại http://127.0.0.1:8000/demo
    - Cho phép chọn THIẾT BỊ CẢM BIẾN THỰC TẾ TRONG FIRESTORE để áp đặt chỉ số tùy ý.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🌿 PlanCare AIoT - Bảng Điều Khiển Demo Giảng Viên</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #10b981;
                --primary-dark: #059669;
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text: #f8fafc;
                --subtext: #94a3b8;
                --border: #334155;
                --danger: #ef4444;
                --warning: #f59e0b;
                --info: #3b82f6;
            }
            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 24px;
                display: flex;
                justify-content: center;
            }
            .container {
                max-width: 800px;
                width: 100%;
            }
            .header {
                text-align: center;
                margin-bottom: 24px;
            }
            .header h1 {
                font-size: 26px;
                margin: 0 0 8px 0;
                color: var(--primary);
            }
            .header p {
                color: var(--subtext);
                font-size: 14px;
                margin: 0;
            }
            .card {
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
            }
            .card-title {
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 16px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            select, input[type="number"], button {
                font-family: inherit;
            }
            select {
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                background: #0f172a;
                color: #fff;
                border: 1px solid var(--border);
                font-size: 15px;
                outline: none;
            }
            .preset-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 12px;
            }
            .btn-preset {
                padding: 12px;
                border-radius: 10px;
                border: 1px solid var(--border);
                background: #0f172a;
                color: #fff;
                cursor: pointer;
                text-align: left;
                transition: all 0.2s;
                font-size: 13px;
                font-weight: 600;
            }
            .btn-preset:hover {
                border-color: var(--primary);
                background: #1e293b;
                transform: translateY(-2px);
            }
            .btn-preset.danger { border-left: 4px solid var(--danger); }
            .btn-preset.warning { border-left: 4px solid var(--warning); }
            .btn-preset.info { border-left: 4px solid var(--info); }
            .btn-preset.success { border-left: 4px solid var(--primary); }

            .slider-group {
                margin-bottom: 16px;
            }
            .slider-header {
                display: flex;
                justify-content: space-between;
                font-size: 14px;
                margin-bottom: 6px;
            }
            input[type="range"] {
                width: 100%;
                accent-color: var(--primary);
            }
            .npk-grid {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 10px;
            }
            .btn-submit {
                width: 100%;
                padding: 14px;
                border-radius: 12px;
                border: none;
                background: var(--primary);
                color: #000;
                font-weight: 700;
                font-size: 16px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .btn-submit:hover {
                background: var(--primary-dark);
                color: #fff;
            }
            #status-box {
                display: none;
                padding: 14px;
                border-radius: 10px;
                font-size: 14px;
                margin-top: 16px;
            }
            .status-success { background: rgba(16, 185, 129, 0.2); border: 1px solid var(--primary); color: #6ee7b7; }
            .status-error { background: rgba(239, 68, 68, 0.2); border: 1px solid var(--danger); color: #fca5a5; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📡 PlanCare AIoT Sensor Demo Panel</h1>
                <p>Can Thiệp Chỉ Số Thiết Bị Cảm Biến Thời Gian Thực Cho Đồ Án</p>
            </div>

            <div class="card">
                <div class="card-title">📡 1. Chọn Thiết Bị Cảm Biến Cần Can Thiệp</div>
                <select id="sensorSelect">
                    <option value="">Đang tải danh sách thiết bị cảm biến từ Firestore...</option>
                </select>
            </div>

            <div class="card">
                <div class="card-title">⚡ 2. Kịch Bản Giả Lập Tức Thời (1-Click Demo Presets)</div>
                <div class="preset-grid">
                    <button class="btn-preset danger" onclick="applyPreset(38.5, 75.0, 50, 30, 40)">🔥 Nắng Nóng (38.5°C)</button>
                    <button class="btn-preset warning" onclick="applyPreset(28.0, 35.0, 50, 30, 40)">🌵 Đất Khô Hạn (35.0%)</button>
                    <button class="btn-preset info" onclick="applyPreset(26.0, 92.0, 50, 30, 40)">💧 Ngập Úng Rễ (92.0%)</button>
                    <button class="btn-preset danger" onclick="applyPreset(28.0, 75.0, 15, 8, 10)">🍂 Suy Kiệt NPK (15/8/10)</button>
                    <button class="btn-preset success" onclick="applyPreset(25.0, 75.0, 55, 32, 42)">🟢 Lý Tưởng Chuẩn (25°C, 75%)</button>
                </div>
            </div>

            <div class="card">
                <div class="card-title">🎛️ 3. Tùy Chỉnh Thông Số Cảm Biến Tùy Ý (Sliders)</div>

                <div class="slider-group">
                    <div class="slider-header">
                        <span>🌡️ Nhiệt độ môi trường (°C)</span>
                        <strong id="tempVal">28.0 °C</strong>
                    </div>
                    <input type="range" id="tempInput" min="15" max="45" step="0.5" value="28.0" oninput="document.getElementById('tempVal').innerText = this.value + ' °C'">
                </div>

                <div class="slider-group">
                    <div class="slider-header">
                        <span>💧 Độ ẩm đất (%)</span>
                        <strong id="humVal">75.0 %</strong>
                    </div>
                    <input type="range" id="humInput" min="10" max="100" step="1" value="75.0" oninput="document.getElementById('humVal').innerText = this.value + ' %'">
                </div>

                <div class="slider-group">
                    <div class="slider-header"><span>🧪 Dinh dưỡng NPK (mg/kg)</span></div>
                    <div class="npk-grid">
                        <div>
                            <span style="font-size: 12px; color: var(--subtext);">Nitơ (N)</span>
                            <input type="number" id="npkN" value="50" style="width: 100%; padding: 8px; border-radius: 6px; background: #0f172a; border: 1px solid var(--border); color: #fff;">
                        </div>
                        <div>
                            <span style="font-size: 12px; color: var(--subtext);">Phốt pho (P)</span>
                            <input type="number" id="npkP" value="30" style="width: 100%; padding: 8px; border-radius: 6px; background: #0f172a; border: 1px solid var(--border); color: #fff;">
                        </div>
                        <div>
                            <span style="font-size: 12px; color: var(--subtext);">Kali (K)</span>
                            <input type="number" id="npkK" value="40" style="width: 100%; padding: 8px; border-radius: 6px; background: #0f172a; border: 1px solid var(--border); color: #fff;">
                        </div>
                    </div>
                </div>

                <button class="btn-submit" onclick="submitCustomOverride()">🚀 Can Thiệp Cảm Biến & Đẩy Lên Firestore</button>

                <div id="status-box"></div>
            </div>
        </div>

        <script>
            async function loadSensors() {
                try {
                    const res = await fetch('/api/sensors');
                    const data = await res.json();
                    const select = document.getElementById('sensorSelect');
                    select.innerHTML = '';
                    
                    if (data.data && data.data.length > 0) {
                        data.data.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s.sensor_id;
                            const plantInfo = s.current_plant_name ? ` ➔ 🪴 Gắn với: ${s.current_plant_name}` : ' ➔ ⚪ Chưa gắn chậu';
                            opt.innerText = `${s.name} (${s.sensor_id})${plantInfo}`;
                            select.appendChild(opt);
                        });
                    } else {
                        const opt = document.createElement('option');
                        opt.value = "sensor_01";
                        opt.innerText = "Cảm biến #1 (sensor_01)";
                        select.appendChild(opt);
                    }
                } catch (e) {
                    console.error("Lỗi tải cảm biến:", e);
                }
            }

            function applyPreset(temp, hum, n, p, k) {
                document.getElementById('tempInput').value = temp;
                document.getElementById('tempVal').innerText = temp + ' °C';
                document.getElementById('humInput').value = hum;
                document.getElementById('humVal').innerText = hum + ' %';
                document.getElementById('npkN').value = n;
                document.getElementById('npkP').value = p;
                document.getElementById('npkK').value = k;

                submitCustomOverride();
            }

            async function submitCustomOverride() {
                const sensorId = document.getElementById('sensorSelect').value;
                if (!sensorId) {
                    showStatus("Vui lòng chọn thiết bị cảm biến!", false);
                    return;
                }

                const payload = {
                    sensor_id: sensorId,
                    temperature: parseFloat(document.getElementById('tempInput').value),
                    soil_humidity: parseFloat(document.getElementById('humInput').value),
                    n: parseFloat(document.getElementById('npkN').value),
                    p: parseFloat(document.getElementById('npkP').value),
                    k: parseFloat(document.getElementById('npkK').value)
                };

                try {
                    const res = await fetch('/api/simulator/override', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if (data.success) {
                        showStatus(`✅ ${data.message}`, true);
                    } else {
                        showStatus(`❌ ${data.error || data.detail}`, false);
                    }
                } catch (e) {
                    showStatus(`❌ Lỗi kết nối máy chủ: ${e.message}`, false);
                }
            }

            function showStatus(msg, isSuccess) {
                const box = document.getElementById('status-box');
                box.style.display = 'block';
                box.className = isSuccess ? 'status-success' : 'status-error';
                box.innerText = msg;
            }

            window.onload = loadSensors;
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
