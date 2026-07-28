import os
import uuid
import base64
import time
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from typing import Optional
from app.models.schemas import ResponseModel

router = APIRouter(prefix="/api/upload", tags=["File Uploads"])

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "uploads"))
os.makedirs(UPLOADS_DIR, exist_ok=True)

class Base64UploadRequest(BaseModel):
    image_base64: str
    filename: Optional[str] = "image.jpg"

@router.post("", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload file ảnh từ ứng dụng (Form-data multipart).
    Lưu file vào máy chủ và trả về đường dẫn URL tĩnh.
    """
    try:
        ext = os.path.splitext(file.filename or "image.jpg")[1]
        if not ext:
            ext = ".jpg"
        
        unique_filename = f"img_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(UPLOADS_DIR, unique_filename)

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        relative_url = f"/static/uploads/{unique_filename}"
        return ResponseModel(
            success=True,
            data={
                "url": relative_url,
                "filename": unique_filename
            },
            message="Tải ảnh lên máy chủ thành công!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tải ảnh lên: {str(e)}"
        )

@router.post("/base64", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def upload_base64_file(body: Base64UploadRequest):
    """
    Upload file ảnh dạng chuỗi Base64 từ ứng dụng.
    """
    try:
        raw_data = body.image_base64
        if "," in raw_data:
            raw_data = raw_data.split(",")[1]

        image_bytes = base64.b64decode(raw_data)
        
        ext = os.path.splitext(body.filename or "image.jpg")[1]
        if not ext:
            ext = ".jpg"

        unique_filename = f"img_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(UPLOADS_DIR, unique_filename)

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        relative_url = f"/static/uploads/{unique_filename}"
        return ResponseModel(
            success=True,
            data={
                "url": relative_url,
                "filename": unique_filename
            },
            message="Tải ảnh Base64 lên máy chủ thành công!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi tải ảnh Base64: {str(e)}"
        )
