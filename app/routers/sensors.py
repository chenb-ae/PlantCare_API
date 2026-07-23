from fastapi import APIRouter, HTTPException, status
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
    Khởi tạo tự động 2 thiết bị cảm biến mẫu nếu chưa có trong Firestore.
    """
    for s_info in DEFAULT_SENSORS:
        doc_ref = db.collection("sensors").document(s_info["sensor_id"])
        if not doc_ref.get().exists:
            doc_ref.set({
                "sensorId": s_info["sensor_id"],
                "name": s_info["name"],
                "code": s_info["code"],
                "tempOffset": s_info["temp_offset"],
                "humidityOffset": s_info["humidity_offset"],
                "status": "available",
                "currentPlantId": None,
                "createdAt": SERVER_TIMESTAMP
            })

@router.get("", response_model=ResponseModel)
async def list_sensors():
    """
    Lấy danh sách các thiết bị cảm biến sẵn có (Phục vụ dropdown chọn cảm biến khi người dùng tạo Plan trồng mới).
    """
    try:
        helper_ensure_default_sensors_exist()

        sensors_stream = db.collection("sensors").stream()
        results = []

        for doc in sensors_stream:
            data = doc.to_dict()
            s_id = doc.id
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
