import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth

def initialize_firebase():
    """
    Khởi tạo Firebase Admin SDK:
    - Tìm file serviceAccountKey.json ở các đường dẫn khả thi.
    - Nếu không thấy, kiểm tra biến môi trường FIREBASE_CREDENTIALS.
    - Nếu vẫn không thấy, sử dụng Application Default Credentials.
    """
    if not firebase_admin._apps:
        # Đường dẫn khả thi tới serviceAccountKey.json
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'serviceAccountKey.json'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'serviceAccountKey.json'),
            'serviceAccountKey.json',
            '/app/serviceAccountKey.json'
        ]
        
        cred = None
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                print(f"[Firebase] Khoi tao Firebase Admin SDK tu file: {abs_path}")
                cred = credentials.Certificate(abs_path)
                break

        # Nếu không có file local (khi chạy trên Vercel), đọc từ biến môi trường FIREBASE_CREDENTIALS
        if not cred:
            firebase_env = os.environ.get("FIREBASE_CREDENTIALS")
            if firebase_env:
                try:
                    firebase_env_str = firebase_env.strip()
                    if firebase_env_str.startswith("'") and firebase_env_str.endswith("'"):
                        firebase_env_str = firebase_env_str[1:-1]

                    try:
                        cred_dict = json.loads(firebase_env_str)
                    except Exception:
                        import base64
                        decoded_bytes = base64.b64decode(firebase_env_str)
                        cred_dict = json.loads(decoded_bytes.decode('utf-8'))

                    if isinstance(cred_dict, dict) and "private_key" in cred_dict:
                        pk = cred_dict["private_key"]
                        if "\\n" in pk:
                            cred_dict["private_key"] = pk.replace("\\n", "\n")

                    cred = credentials.Certificate(cred_dict)
                    print("[Firebase] Khoi tao Firebase Admin SDK tu bien moi truong FIREBASE_CREDENTIALS thanh cong!")
                except Exception as e:
                    print(f"[Firebase Warning] Khong the doc FIREBASE_CREDENTIALS: {e}")
                
        if cred:
            firebase_admin.initialize_app(cred)
        else:
            print("[Firebase] Khoi tao Firebase Admin SDK bang Application Default Credentials (Cloud Run)")
            firebase_admin.initialize_app()

initialize_firebase()

# Firestore Database Client
db = firestore.client()

def get_db():
    return db
