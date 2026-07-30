from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from google.cloud.firestore import SERVER_TIMESTAMP
from app.config.firebase import db
from app.models.schemas import ResponseModel, SensorDeviceResponse

router = APIRouter(prefix="/api/sensors", tags=["Hardware Sensor Devices"])

DEFAULT_SENSORS = [
    {
        "sensor_id": "sensor_01",
        "name": "Cảm biến #1 (Ban công - ESP32 A1)",
        "code": "ESP32-A1-BALCONY",
        "temp_offset": 0.0,
        "humidity_offset": 0.0
    },
    {
        "sensor_id": "sensor_02",
        "name": "Cảm biến #2 (Sân thượng - ESP32 B2)",
        "code": "ESP32-B2-ROOFTOP",
        "temp_offset": 1.2,  # Sân thượng thường nóng hơn ban công 1.2°C
        "humidity_offset": -3.0 # Sân thượng gió hơn nên khô hơn 3%
    }
]

def helper_ensure_default_sensors_exist():
    """
    Không tự động tạo 2 cảm biến mặc định nữa (User tự quản lý cảm biến của riêng mình).
    """
    pass

from typing import Optional

@router.get("", response_model=ResponseModel)
async def list_sensors(
    user_id: Optional[str] = Query(None, alias="userId", description="Mã người dùng để lọc cảm biến cá nhân")
):
    """
    Lấy danh sách các thiết bị cảm biến cá nhân của người dùng.
    """
    try:
        sensors_stream = db.collection("sensors").stream()
        results = []

        for doc in sensors_stream:
            data = doc.to_dict()
            s_id = doc.id
            s_user = data.get("userId")

            # Bỏ 2 cảm biến mặc định khỏi UI
            if s_id in ["sensor_01", "sensor_02"]:
                continue

            # Mỗi user CHỈ nhìn thấy & sử dụng cảm biến do chính họ tự tạo!
            if user_id and s_user != user_id:
                continue

            plant_id = data.get("currentPlantId")
            plant_name = None

            if plant_id:
                p_doc = db.collection("plants").document(plant_id).get()
                if p_doc.exists:
                    plant_name = p_doc.to_dict().get("name")

            status_val = "assigned" if plant_id else "available"

            results.append({
                "sensor_id": s_id,
                "name": data.get("name", f"Cảm biến {s_id}"),
                "code": data.get("code", s_id.upper()),
                "status": status_val,
                "user_id": s_user,
                "current_plant_id": plant_id,
                "current_plant_name": plant_name
            })

        results.sort(key=lambda x: x["sensor_id"])

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} thiết bị cảm biến."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách cảm biến: {str(e)}"
        )

@router.get("/{sensor_id}", response_model=ResponseModel)
async def get_sensor_detail(sensor_id: str):
    """
    Lấy thông tin chi tiết một thiết bị cảm biến.
    """
    try:
        doc_ref = db.collection("sensors").document(sensor_id).get()
        if not doc_ref.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy thiết bị cảm biến '{sensor_id}'."
            )

        data = doc_ref.to_dict()
        plant_id = data.get("currentPlantId")
        plant_name = None
        if plant_id:
            p_doc = db.collection("plants").document(plant_id).get()
            if p_doc.exists:
                plant_name = p_doc.to_dict().get("name")

        return ResponseModel(
            success=True,
            data={
                "sensor_id": sensor_id,
                "name": data.get("name"),
                "code": data.get("code"),
                "status": "assigned" if plant_id else "available",
                "user_id": data.get("userId"),
                "current_plant_id": plant_id,
                "current_plant_name": plant_name
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy thông tin cảm biến: {str(e)}"
        )

@router.post("/seed", response_model=ResponseModel)
async def seed_sensors():
    """
    API Khôi phục/khởi tạo lại danh sách cảm biến mặc định (sensor_01 & sensor_02).
    """
    try:
        helper_ensure_default_sensors_exist()
        return ResponseModel(
            success=True,
            data={"sensors": [s["sensor_id"] for s in DEFAULT_SENSORS]},
            message="Khởi tạo thành công 2 cảm biến mặc định (sensor_01 và sensor_02)!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khởi tạo cảm biến: {str(e)}"
        )

class CreateSensorRequest(BaseModel):
    sensor_id: str = Field(None, description="Mã cảm biến (ví dụ: sensor_03). Tự động sinh nếu để trống.")
    user_id: str = Field(None, description="Mã người dùng sở hữu cảm biến", example="user_123")
    name: str = Field(..., description="Tên cảm biến", example="Cảm biến #3 (Cửa sổ phòng khách)")
    code: str = Field(None, description="Mã thiết bị", example="ESP32-C3-WINDOW")
    temp_offset: float = Field(0.0, description="Độ lệch nhiệt độ", example=0.0)
    humidity_offset: float = Field(0.0, description="Độ lệch độ ẩm", example=0.0)

@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def create_sensor(body: CreateSensorRequest):
    """
    API Thêm thiết bị cảm biến phần cứng mới (Phục vụ việc người dùng tự thêm cảm biến cá nhân):
    - Tự động sinh `sensor_id` nếu người dùng không truyền vào.
    - Khởi tạo trạng thái `available` và tạo dữ liệu khởi chạy ban đầu cho cảm biến.
    """
    try:
        if not body.sensor_id:
            existing_sensor_ids = set(doc.id for doc in db.collection("sensors").stream())
            count = len(existing_sensor_ids) + 1
            sensor_id = f"sensor_{count:02d}"
            while sensor_id in existing_sensor_ids:
                count += 1
                sensor_id = f"sensor_{count:02d}"
        else:
            sensor_id = body.sensor_id

        doc_ref = db.collection("sensors").document(sensor_id)
        doc_data = {
            "sensorId": sensor_id,
            "userId": body.user_id,
            "name": body.name,
            "code": body.code or sensor_id.upper(),
            "tempOffset": body.temp_offset,
            "humidityOffset": body.humidity_offset,
            "status": "available",
            "currentPlantId": None,
            "createdAt": SERVER_TIMESTAMP
        }
        doc_ref.set(doc_data)

        # Tạo chỉ số dữ liệu khởi đầu cho cảm biến mới theo tiêu chuẩn tối ưu
        initial_reading = {
            "sensorId": sensor_id,
            "plantId": None,
            "timestamp": SERVER_TIMESTAMP,
            "temperature": 27.0,
            "soilHumidity": 75.0,
            "npk": {"n": 80.0, "p": 50.0, "k": 130.0}
        }
        db.collection("sensor_readings").add(initial_reading)

        return ResponseModel(
            success=True,
            data={
                "sensor_id": sensor_id,
                "user_id": body.user_id,
                "name": body.name,
                "code": body.code or sensor_id.upper(),
                "status": "available"
            },
            message=f"Đã tạo mới thiết bị cảm biến '{body.name}' ({sensor_id}) thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tạo mới cảm biến: {str(e)}"
        )

@router.delete("/{sensor_id}", response_model=ResponseModel)
async def delete_sensor(sensor_id: str):
    """
    Xóa thiết bị cảm biến khỏi hệ thống.
    """
    try:
        doc_ref = db.collection("sensors").document(sensor_id)
        s_doc = doc_ref.get()
        if not s_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy cảm biến '{sensor_id}'"
            )

        data = s_doc.to_dict()
        current_plant_id = data.get("currentPlantId")
        if current_plant_id:
            p_ref = db.collection("plants").document(current_plant_id)
            if p_ref.get().exists:
                p_ref.update({"sensorId": None})

        doc_ref.delete()
        return ResponseModel(
            success=True,
            data={"sensor_id": sensor_id},
            message=f"Đã xóa thiết bị cảm biến '{sensor_id}' thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xóa cảm biến: {str(e)}"
        )
