from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import Query as FirestoreQuery
from app.config.firebase import db
from app.models.schemas import ResponseModel, SensorReadingResponse
import datetime

router = APIRouter(prefix="/api/sensor-readings", tags=["Sensor Readings & Charts"])

@router.get("/latest/{plant_id}", response_model=ResponseModel)
async def get_latest_sensor_reading(plant_id: str):
    """
    Lấy chỉ số cảm biến thời gian thực mới nhất của một chậu cây (Hiển thị thẻ chỉ số trên màn hình Chi tiết chậu cây).
    """
    try:
        readings_stream = db.collection("sensor_readings").where("plantId", "==", plant_id).stream()
        readings = []
        for doc in readings_stream:
            d = doc.to_dict()
            d["_doc_id"] = doc.id
            readings.append(d)

        if not readings:
            return ResponseModel(success=True, data=None, message="Chưa có dữ liệu cảm biến.")

        def get_ts(x):
            ts = x.get("timestamp")
            if hasattr(ts, "timestamp"):
                return ts.timestamp()
            return str(ts or "")

        readings.sort(key=get_ts, reverse=True)
        data = readings[0]
        ts_val = data.get("timestamp")
        ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)

        return ResponseModel(
            success=True,
            data={
                "reading_id": data["_doc_id"],
                "plant_id": plant_id,
                "sensor_id": data.get("sensorId", "sensor_01"),
                "timestamp": ts_str,
                "temperature": float(data.get("temperature", 0.0)),
                "soil_humidity": float(data.get("soilHumidity", 0.0)),
                "npk": data.get("npk", {"n": 0.0, "p": 0.0, "k": 0.0})
            }
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có dữ liệu cảm biến cho cây này."
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy thông số cảm biến mới nhất: {str(e)}"
        )

@router.get("/history/{plant_id}", response_model=ResponseModel)
async def get_sensor_history(
    plant_id: str,
    limit: int = Query(50, ge=1, le=500, description="Số điểm dữ liệu tối đa"),
    hours: int = Query(None, ge=1, le=720, description="Lọc điểm dữ liệu trong N giờ gần nhất")
):
    """
    Lấy lịch sử thông số cảm biến phục vụ vẽ biểu đồ biến thiên theo mã cây (`plant_id`).
    """
    try:
        readings_stream = db.collection("sensor_readings").where("plantId", "==", plant_id).stream()
        results = []

        cutoff = None
        if hours:
            cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

        for doc in readings_stream:
            data = doc.to_dict()
            ts_val = data.get("timestamp")
            
            if cutoff and ts_val:
                dt_val = ts_val if isinstance(ts_val, datetime.datetime) else None
                if dt_val and dt_val < cutoff:
                    continue

            ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)

            results.append({
                "reading_id": doc.id,
                "plant_id": plant_id,
                "sensor_id": data.get("sensorId", "sensor_01"),
                "timestamp": ts_str,
                "temperature": float(data.get("temperature", 0.0)),
                "soil_humidity": float(data.get("soilHumidity", 0.0)),
                "npk": data.get("npk", {"n": 0.0, "p": 0.0, "k": 0.0})
            })

        results.sort(key=lambda x: str(x["timestamp"]), reverse=True)
        if limit:
            results = results[:limit]

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} điểm dữ liệu lịch sử cảm biến."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy lịch sử cảm biến: {str(e)}"
        )

@router.get("/by-sensor/{sensor_id}", response_model=ResponseModel)
async def get_sensor_history_by_sensor(
    sensor_id: str,
    limit: int = Query(50, ge=1, le=500, description="Số điểm dữ liệu tối đa")
):
    """
    Lấy lịch sử thông số cảm biến riêng trực tiếp theo mã cảm biến (`sensor_id`).
    """
    try:
        readings_stream = db.collection("sensor_readings").where("sensorId", "==", sensor_id).stream()
        results = []

        for doc in readings_stream:
            data = doc.to_dict()
            ts_val = data.get("timestamp")
            ts_str = ts_val.isoformat() if hasattr(ts_val, "isoformat") else str(ts_val)

            results.append({
                "reading_id": doc.id,
                "plant_id": data.get("plantId"),
                "sensor_id": sensor_id,
                "timestamp": ts_str,
                "temperature": float(data.get("temperature", 0.0)),
                "soil_humidity": float(data.get("soilHumidity", 0.0)),
                "npk": data.get("npk", {"n": 0.0, "p": 0.0, "k": 0.0})
            })

        results.sort(key=lambda x: str(x["timestamp"]), reverse=True)
        if limit:
            results = results[:limit]

        return ResponseModel(
            success=True,
            data=results,
            message=f"Đã lấy {len(results)} điểm dữ liệu cảm biến cho {sensor_id}."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy lịch sử cảm biến: {str(e)}"
        )
