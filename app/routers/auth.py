from fastapi import APIRouter, HTTPException, status
from google.cloud.firestore import SERVER_TIMESTAMP
from app.config.firebase import db
from app.models.schemas import (
    ResponseModel, UserRegisterRequest, UserLoginRequest, 
    UserUpdateRequest, UserProfileResponse
)
from firebase_admin import auth as firebase_auth
import datetime

router = APIRouter(prefix="/api/auth", tags=["Auth & User Profile"])

@router.post("/register", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def register_user(body: UserRegisterRequest):
    """
    Đăng ký tài khoản người dùng mới:
    - Tạo user trong Firebase Auth (nếu có email/password).
    - Tạo document lưu trữ thông tin tài khoản trong collection Firestore `/users/{user_id}`.
    """
    try:
        user_id = None
        # Thử tạo user trên Firebase Auth nếu email chưa tồn tại
        try:
            user_record = firebase_auth.create_user(
                email=body.email,
                password=body.password or "defaultPass123",
                display_name=body.name
            )
            user_id = user_record.uid
        except Exception as auth_err:
            # Nếu user đã tồn tại trong Firebase Auth, tìm theo email
            try:
                existing_user = firebase_auth.get_user_by_email(body.email)
                user_id = existing_user.uid
            except Exception:
                # Nếu không tìm thấy trong auth, tự sinh ID cho demo
                user_id = f"user_{int(datetime.datetime.now().timestamp())}"

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        user_data = {
            "name": body.name,
            "email": body.email,
            "createdAt": SERVER_TIMESTAMP
        }
        
        db.collection("users").document(user_id).set(user_data, merge=True)
        
        return ResponseModel(
            success=True,
            data={
                "user_id": user_id,
                "name": body.name,
                "email": body.email,
                "created_at": now_iso
            },
            message="Đăng ký tài khoản thành công!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đăng ký tài khoản: {str(e)}"
        )

@router.post("/login", response_model=ResponseModel)
async def login_user(body: UserLoginRequest):
    """
    Đăng nhập tài khoản người dùng:
    - Tìm kiếm tài khoản trong Firestore theo Email.
    - Trả về thông tin cá nhân của người dùng.
    """
    try:
        users_ref = db.collection("users").where("email", "==", body.email).limit(1).stream()
        user_doc = None
        for doc in users_ref:
            user_doc = doc
            break

        if not user_doc:
            # Tìm trong Firebase Auth nếu chưa có document Firestore
            try:
                fb_user = firebase_auth.get_user_by_email(body.email)
                user_id = fb_user.uid
                name = fb_user.display_name or body.email.split("@")[0]
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                # Tạo document mới
                db.collection("users").document(user_id).set({
                    "name": name,
                    "email": body.email,
                    "createdAt": SERVER_TIMESTAMP
                })
                
                return ResponseModel(
                    success=True,
                    data={
                        "user_id": user_id,
                        "name": name,
                        "email": body.email,
                        "created_at": now_iso
                    },
                    message="Đăng nhập thành công!"
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_444_NOT_FOUND if hasattr(status, 'HTTP_444_NOT_FOUND') else status.HTTP_404_NOT_FOUND,
                    detail="Tài khoản không tồn tại. Vui lòng đăng ký!"
                )

        u_data = user_doc.to_dict()
        created_at_val = u_data.get("createdAt")
        created_at_str = created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val)

        return ResponseModel(
            success=True,
            data={
                "user_id": user_doc.id,
                "name": u_data.get("name", ""),
                "email": u_data.get("email", ""),
                "created_at": created_at_str
            },
            message="Đăng nhập thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đăng nhập: {str(e)}"
        )

@router.get("/profile/{user_id}", response_model=ResponseModel)
async def get_user_profile(user_id: str):
    """
    Lấy thông tin chi tiết hồ sơ cá nhân của người dùng từ Firestore.
    """
    try:
        doc_ref = db.collection("users").document(user_id).get()
        if not doc_ref.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng."
            )

        data = doc_ref.to_dict()
        created_at_val = data.get("createdAt")
        created_at_str = created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val)

        return ResponseModel(
            success=True,
            data={
                "user_id": doc_ref.id,
                "name": data.get("name", ""),
                "email": data.get("email", ""),
                "created_at": created_at_str
            }
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy thông tin hồ sơ: {str(e)}"
        )

@router.put("/profile/{user_id}", response_model=ResponseModel)
async def update_user_profile(user_id: str, body: UserUpdateRequest):
    """
    Cập nhật thông tin hồ sơ cá nhân của người dùng.
    """
    try:
        doc_ref = db.collection("users").document(user_id)
        if not doc_ref.get().exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng để cập nhật."
            )

        update_fields = {}
        if body.name is not None:
            update_fields["name"] = body.name

        if update_fields:
            doc_ref.update(update_fields)

        updated_doc = doc_ref.get().to_dict()
        created_at_val = updated_doc.get("createdAt")
        created_at_str = created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val)

        return ResponseModel(
            success=True,
            data={
                "user_id": user_id,
                "name": updated_doc.get("name", ""),
                "email": updated_doc.get("email", ""),
                "created_at": created_at_str
            },
            message="Cập nhật hồ sơ thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật hồ sơ: {str(e)}"
        )
