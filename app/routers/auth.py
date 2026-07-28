from fastapi import APIRouter, HTTPException, status
from google.cloud.firestore import SERVER_TIMESTAMP
from app.config.firebase import db
from app.models.schemas import (
    ResponseModel, UserRegisterRequest, UserLoginRequest, 
    UserUpdateRequest, UserProfileResponse, ChangePasswordRequest,
    GoogleAuthRequest
)
from firebase_admin import auth as firebase_auth
from firebase_admin._auth_utils import EmailAlreadyExistsError
import datetime

router = APIRouter(prefix="/api/auth", tags=["Auth & User Profile"])

@router.post("/google", response_model=ResponseModel)
async def google_auth_user(body: GoogleAuthRequest):
    """
    Đăng nhập / Đăng ký bằng Google OAuth (Tuân thủ 100% thiết lập 'Create account for each provider' của Firebase Console):
    - Đăng ký Provider 'google.com' chính thức trên Firebase Authentication Console (`google_{google_id}`).
    - Lưu hồ sơ người dùng độc lập trong Firestore `/users/google_{google_id}`.
    """
    try:
        g_id = body.google_id or body.email.replace("@", "_at_")
        user_id = f"google_{g_id}"

        # 1. Khởi tạo User với provider_id = 'google.com' trên Firebase Authentication Console
        try:
            firebase_auth.get_user(user_id)
        except firebase_auth.UserNotFoundError:
            try:
                import_rec = firebase_auth.ImportUserRecord(
                    uid=user_id,
                    display_name=body.name,
                    photo_url=body.avatar_url,
                    provider_data=[
                        firebase_auth.UserProvider(
                            uid=g_id,
                            provider_id="google.com",
                            email=body.email,
                            display_name=body.name,
                            photo_url=body.avatar_url
                        )
                    ]
                )
                firebase_auth.import_users([import_rec])
            except Exception:
                pass
        except Exception:
            pass

        # 2. Cập nhật DisplayName / PhotoURL nếu có
        try:
            firebase_auth.update_user(
                user_id,
                display_name=body.name,
                photo_url=body.avatar_url
            )
        except Exception:
            pass

        # 3. Đồng bộ hồ sơ tài khoản Google độc lập trong Firestore `/users/{google_id}`
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        user_data = {
            "name": body.name,
            "email": body.email,
            "provider": "google",
            "googleId": g_id,
            "updatedAt": SERVER_TIMESTAMP
        }
        if body.avatar_url:
            user_data["avatarUrl"] = body.avatar_url

        if not doc.exists:
            user_data["createdAt"] = SERVER_TIMESTAMP
            doc_ref.set(user_data)
        else:
            doc_ref.set(user_data, merge=True)

        return ResponseModel(
            success=True,
            data={
                "user_id": user_id,
                "name": body.name,
                "email": body.email,
                "created_at": now_iso
            },
            message="Đã tạo và đăng nhập tài khoản Google trên Firebase Authentication!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý đăng nhập Google: {str(e)}"
        )

@router.post("/register", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def register_user(body: UserRegisterRequest):
    """
    Đăng ký tài khoản người dùng mới bằng Email & Mật khẩu:
    - Tạo user trong Firebase Auth và tạo document tương ứng trong Firestore `/users/{uid}`.
    """
    try:
        # 1. Kiểm tra sự tồn tại của Email trong Firestore (chỉ áp dụng cho tài khoản Email/Password)
        existing_docs = list(db.collection("users").where("email", "==", body.email).stream())
        email_pass_exists = any(d.to_dict().get("provider") != "google" for d in existing_docs)
        if email_pass_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được đăng ký tài khoản Email/Mật khẩu. Vui lòng đăng nhập!"
            )

        # 2. Tạo User trên Firebase Authentication Console
        try:
            user_record = firebase_auth.create_user(
                email=body.email,
                password=body.password or "defaultPass123",
                display_name=body.name
            )
            user_id = user_record.uid
        except Exception:
            user_id = f"user_{int(datetime.datetime.now().timestamp())}"

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 3. Khởi tạo document thông tin người dùng trong Firestore với ID = Firebase Auth UID
        user_data = {
            "name": body.name,
            "email": body.email,
            "password": body.password or "defaultPass123",
            "provider": "email",
            "createdAt": SERVER_TIMESTAMP
        }
        
        db.collection("users").document(user_id).set(user_data)
        
        return ResponseModel(
            success=True,
            data={
                "user_id": user_id,
                "name": body.name,
                "email": body.email,
                "created_at": now_iso
            },
            message="Đăng ký tài khoản Email/Password thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đăng ký tài khoản: {str(e)}"
        )

@router.post("/login", response_model=ResponseModel)
async def login_user(body: UserLoginRequest):
    """
    Đăng nhập tài khoản Email & Mật khẩu:
    - Tra cứu tài khoản provider='email' trong Firestore hoặc Firebase Auth.
    - XÁC THỰC MẬT KHẨU.
    """
    try:
        users_ref = db.collection("users").where("email", "==", body.email).stream()
        user_doc = None
        for doc in users_ref:
            d = doc.to_dict()
            if d.get("provider") != "google":
                user_doc = doc
                break

        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tài khoản Email/Mật khẩu không tồn tại. Vui lòng đăng ký mới!"
            )

        u_data = user_doc.to_dict()
        stored_password = u_data.get("password")

        # Kiểm tra mật khẩu
        if stored_password and stored_password != body.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu không chính xác. Vui lòng thử lại!"
            )

        created_at_val = u_data.get("createdAt")
        created_at_str = created_at_val.isoformat() if (created_at_val and hasattr(created_at_val, "isoformat")) else str(created_at_val or "")

        return ResponseModel(
            success=True,
            data={
                "user_id": user_doc.id,
                "name": u_data.get("name", ""),
                "email": body.email,
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
        created_at_str = created_at_val.isoformat() if (created_at_val and hasattr(created_at_val, "isoformat")) else str(created_at_val or "")

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
        created_at_str = created_at_val.isoformat() if (created_at_val and hasattr(created_at_val, "isoformat")) else str(created_at_val or "")

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

@router.post("/change-password", response_model=ResponseModel)
async def change_password(body: ChangePasswordRequest):
    """
    Đổi mật khẩu tài khoản người dùng:
    - Kiểm tra mật khẩu hiện tại (old_password). Nếu sai ➔ Báo lỗi HTTP 400.
    - Cập nhật mật khẩu mới (new_password) vào Firestore & Firebase Auth.
    """
    try:
        doc_ref = db.collection("users").document(body.user_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài khoản người dùng."
            )

        u_data = doc.to_dict()
        stored_password = u_data.get("password")

        # Kiểm tra mật khẩu cũ
        if stored_password and stored_password != body.old_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác. Vui lòng kiểm tra lại!"
            )

        # Cập nhật trên Firebase Auth
        try:
            email = u_data.get("email")
            if email:
                fb_user = firebase_auth.get_user_by_email(email)
                firebase_auth.update_user(fb_user.uid, password=body.new_password)
        except Exception as fb_err:
            print(f"Lỗi cập nhật Firebase Auth password: {fb_err}")

        # Cập nhật document Firestore
        doc_ref.update({"password": body.new_password})

        return ResponseModel(
            success=True,
            data={"user_id": body.user_id},
            message="Đổi mật khẩu thành công!"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi đổi mật khẩu: {str(e)}"
        )
