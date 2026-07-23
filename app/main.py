import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Khởi tạo kết nối Firebase trước khi import routers
import app.config.firebase

# Import tất cả các router phân chia theo từng nhóm chức năng
from app.routers import auth, plants, logs, sensor_readings, alerts, simulator, sensors
from app.routers.sensors import helper_ensure_default_sensors_exist

app = FastAPI(
    title="Lush Intelligence - PlanCare Smart Urban Garden API",
    description="Hệ thống Backend FastAPI cho Ứng dụng Quản lý Vườn rau Đô thị Thông minh (PlanCare / Lush Intelligence)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    # Tự động đảm bảo 2 cảm biến mặc định (sensor_01 & sensor_02) đã được khởi tạo trong Firestore
    try:
        helper_ensure_default_sensors_exist()
        print("[Startup] Da kiem tra va khoi tao 2 thiet bi cam bien mac dinh (sensor_01 & sensor_02)!")
    except Exception as e:
        print(f"[Startup Warning] Khong the tu dong khoi tao sensors: {e}")

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
            "/api/simulator"
        ]
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
