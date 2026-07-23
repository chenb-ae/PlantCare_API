from fastapi import APIRouter, HTTPException, Query, status
from google.cloud.firestore import Query as FirestoreQuery
from app.config.firebase import db
from app.models.schemas import ResponseModel, AlertResponse, UnreadCountResponse

router = APIRouter(prefix="/api/alerts", tags=["Smart Alerts & Notifications"])

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
            user_plant_map[p_doc.id] = p_data.get("name", "Chậu cây")

        if not user_plant_map:
            return ResponseModel(success=True, data=[], message="Người dùng chưa có cây trồng nào.")

        target_plant_ids = [plant_id] if plant_id else list(user_plant_map.keys())

        # Firestore limit 'in' query to 30 items
        results = []
        for i in range(0, len(target_plant_ids), 30):
            batch_ids = target_plant_ids[i:i+30]
            query = db.collection("alerts").where("plantId", "in", batch_ids)
            
            if unread_only:
                query = query.where("isRead", "==", False)

            alerts_stream = query.order_by("timestamp", direction=FirestoreQuery.DESCENDING).limit(100).stream()

            for doc in alerts_stream:
                a_data = doc.to_dict()
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

@router.get("/unread-count", response_model=ResponseModel)
async def get_unread_count(
    user_id: str = Query(..., alias="userId", description="Mã người dùng")
):
    """
    Đếm số lượng cảnh báo chưa đọc của người dùng (Phục vụ hiển thị Badge icon chuông thông báo trên giao diện Flutter).
    """
    try:
        user_plants_stream = db.collection("plants").where("userId", "==", user_id).stream()
        user_plant_ids = [p_doc.id for p_doc in user_plants_stream]

        if not user_plant_ids:
            return ResponseModel(success=True, data={"user_id": user_id, "unread_count": 0})

        unread_count = 0
        for i in range(0, len(user_plant_ids), 30):
            batch_ids = user_plant_ids[i:i+30]
            alerts = (
                db.collection("alerts")
                .where("plantId", "in", batch_ids)
                .where("isRead", "==", False)
                .stream()
            )
            unread_count += len(list(alerts))

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
