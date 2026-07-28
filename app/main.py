import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Khởi tạo kết nối Firebase trước khi import routers
import app.config.firebase

# Import tất cả các router phân chia theo từng nhóm chức năng
from app.routers import auth, plants, logs, sensor_readings, alerts, simulator, sensors, upload
from app.routers.sensors import helper_ensure_default_sensors_exist

app = FastAPI(
    title="Lush Intelligence - PlanCare Smart Urban Garden API",
    description="Hệ thống Backend FastAPI cho Ứng dụng Quản lý Vườn rau Đô thị Thông minh (PlanCare / Lush Intelligence)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── Cấu hình Phục vụ File tĩnh (Uploads) ────────────────────────
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

import asyncio

async def auto_simulator_loop():
    """
    Vòng lặp tự động chạy bộ giả lập suy hao 15 phút một lần trên máy chủ FastAPI.
    """
    await asyncio.sleep(10)  # Đợi 10 giây sau khi server bật
    while True:
        try:
            from app.config.firebase import db
            from app.routers.simulator import helper_run_simulation_for_sensor
            sensors_stream = db.collection("sensors").stream()
            count = 0
            for doc in sensors_stream:
                helper_run_simulation_for_sensor(doc.id, doc.to_dict())
                count += 1
            print(f"[Auto-Simulator 15m] Da tu dong chay gia lap suy hao cho {count} cam bien thanh cong!")
        except Exception as err:
            print(f"[Auto-Simulator Error] {err}")
        await asyncio.sleep(900)  # 900 giây = 15 phút

@app.on_event("startup")
async def startup_event():
    # Tự động đảm bảo 2 cảm biến mặc định (sensor_01 & sensor_02) đã được khởi tạo trong Firestore
    try:
        helper_ensure_default_sensors_exist()
        print("[Startup] Da kiem tra va khoi tao 2 thiet bi cam bien mac dinh (sensor_01 & sensor_02)!")
    except Exception as e:
        print(f"[Startup Warning] Khong the tu dong khoi tao sensors: {e}")

    # Kích hoạt vòng lặp tự động giả lập 15 phút/lần dưới nền máy chủ
    asyncio.create_task(auto_simulator_loop())

# ── Cấu hình CORS cho Flutter App ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Tích hợp các Router nhóm chức năng ──────────────────────────
app.include_router(auth.router)
app.include_router(sensors.router)
app.include_router(plants.router)
app.include_router(logs.router)
app.include_router(sensor_readings.router)
app.include_router(alerts.router)
app.include_router(simulator.router)
app.include_router(upload.router)

# ── Health Check Endpoint ───────────────────────────────────────
@app.get("/", tags=["Health Check"])
async def root_health_check():
    return {
        "status": "ok",
        "service": "Lush Intelligence PlanCare Backend (FastAPI)",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/api/auth",
            "/api/sensors",
            "/api/plants",
            "/api/logs",
            "/api/sensor-readings",
            "/api/alerts",
            "/api/simulator",
            "/api/upload"
        ]
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
