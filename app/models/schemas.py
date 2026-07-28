from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# ── API Standard Response Schema ──────────────────────────────
class ResponseModel(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None

# ── User Schemas ──────────────────────────────────────────────
class UserRegisterRequest(BaseModel):
    name: str = Field(..., example="Nguyễn Văn A")
    email: str = Field(..., example="user@gmail.com")
    password: Optional[str] = Field(None, example="123456")

class UserLoginRequest(BaseModel):
    email: str = Field(..., example="user@gmail.com")
    password: Optional[str] = Field(None, example="123456")

class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, example="Nguyễn Văn A")

class GoogleAuthRequest(BaseModel):
    name: str = Field(..., example="Nguyễn Văn A")
    email: str = Field(..., example="user@gmail.com")
    google_id: Optional[str] = Field(None, example="google_uid_123")
    avatar_url: Optional[str] = Field(None, example="https://lh3.googleusercontent.com/...")

class ChangePasswordRequest(BaseModel):
    user_id: str = Field(..., example="user_123")
    old_password: str = Field(..., example="oldPass123")
    new_password: str = Field(..., example="newPass123")

class UserProfileResponse(BaseModel):
    user_id: str
    name: str
    email: str
    created_at: Optional[str] = None

# ── Sensor Device Schemas ─────────────────────────────────────
class SensorDeviceResponse(BaseModel):
    sensor_id: str = Field(..., example="sensor_01")
    name: str = Field(..., example="Thiết bị Cảm biến #1 (Ban công)")
    code: str = Field(..., example="ESP32-A1")
    status: str = Field(..., example="available", description="available | assigned | inactive")
    current_plant_id: Optional[str] = None
    current_plant_name: Optional[str] = None

# ── NPK Model ────────────────────────────────────────────────
class NPKData(BaseModel):
    n: float = Field(..., description="Nitơ (mg/kg)")
    p: float = Field(..., description="Phốt pho (mg/kg)")
    k: float = Field(..., description="Kali (mg/kg)")

# ── Sensor Reading Schemas ───────────────────────────────────
class SensorReadingResponse(BaseModel):
    reading_id: str
    plant_id: Optional[str] = None
    sensor_id: str
    timestamp: str
    temperature: float = Field(..., description="Nhiệt độ (°C)")
    soil_humidity: float = Field(..., description="Độ ẩm đất (%)")
    npk: NPKData

# ── Plant Schemas ─────────────────────────────────────────────
class PlantCreateRequest(BaseModel):
    user_id: str = Field(..., example="user_123")
    name: str = Field(..., example="Chậu Cải Ngọt Ban Công")
    type: str = Field(..., example="cai_ngot", description="cai_thia | cai_ngot | rau_muong | xa_lach")
    sensor_id: str = Field("sensor_01", example="sensor_01", description="Mã cảm biến chọn để gắn (sensor_01 hoặc sensor_02)")
    placement: Optional[str] = Field("outdoor", example="outdoor", description="outdoor | shaded")
    image_url: Optional[str] = Field(None, example="https://example.com/plant.jpg", description="URL hình ảnh chậu cây")

class PlantUpdateRequest(BaseModel):
    name: Optional[str] = None
    sensor_id: Optional[str] = Field(None, description="Đổi mã cảm biến gắn cho cây")
    placement: Optional[str] = Field(None, description="outdoor | shaded")
    status: Optional[str] = Field(None, description="growing | harvested")
    image_url: Optional[str] = Field(None, description="Cập nhật URL hình ảnh chậu cây/hình thu hoạch")

class PlantResponse(BaseModel):
    plant_id: str
    user_id: str
    name: str
    type: str
    type_label: str
    sensor_id: str
    sensor_name: Optional[str] = None
    image_url: Optional[str] = None
    planted_at: str
    placement: str
    status: str
    harvested_at: Optional[str] = None
    latest_sensor: Optional[SensorReadingResponse] = None
    unread_alert_count: Optional[int] = 0

# ── Care Log Schemas ──────────────────────────────────────────
class LogCreateRequest(BaseModel):
    plant_id: str = Field(..., example="plant_xyz789")
    action: str = Field(..., example="watering", description="watering | fertilizing | shade_covering | sun_exposure | harvesting")
    notes: Optional[str] = Field(None, example="Đã tưới nước buổi sáng")

class LogResponse(BaseModel):
    log_id: str
    plant_id: str
    sensor_id: Optional[str] = None
    action: str
    notes: Optional[str] = ""
    timestamp: str

# ── Alert Schemas ─────────────────────────────────────────────
class AlertResponse(BaseModel):
    alert_id: str
    plant_id: str
    sensor_id: Optional[str] = None
    plant_name: Optional[str] = None
    type: str = Field(..., description="LOW_SOIL_MOISTURE | HIGH_SOIL_MOISTURE | LOW_NPK | HIGH_TEMP | LOW_TEMP")
    message: str
    timestamp: str
    is_read: bool

class UnreadCountResponse(BaseModel):
    user_id: str
    unread_count: int
