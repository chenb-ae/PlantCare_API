import os
import firebase_admin
from firebase_admin import credentials, firestore, auth

def initialize_firebase():
    """
    Khởi tạo Firebase Admin SDK:
    - Ưu tiên đọc JSON từ biến môi trường FIREBASE_CREDENTIALS (Dành cho Vercel / Cloud).
    - Nếu không thấy, tìm file serviceAccountKey.json ở các đường dẫn khả thi.
    - Nếu vẫn không thấy, sử dụng Application Default Credentials (Cloud Run).
    """
    if not firebase_admin._apps:
        cred = None

        # 1. Ưu tiên đọc từ biến môi trường FIREBASE_CREDENTIALS (dành cho Vercel / Cloud)
        firebase_env = os.environ.get("FIREBASE_CREDENTIALS")
        if firebase_env:
            try:
                import json
                cred_dict = json.loads(firebase_env)
                cred = credentials.Certificate(cred_dict)
                print("[Firebase] Khoi tao Firebase Admin SDK tu bien moi truong FIREBASE_CREDENTIALS")
            except Exception as e:
                print(f"[Firebase Warning] Khong the doc FIREBASE_CREDENTIALS: {e}")

        # 2. Nếu không có biến môi trường, tìm file serviceAccountKey.json local
        if not cred:
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'serviceAccountKey.json'),
                os.path.join(os.path.dirname(__file__), '..', '..', 'serviceAccountKey.json'),
                'serviceAccountKey.json',
                '/app/serviceAccountKey.json'
            ]
            
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    print(f"[Firebase] Khoi tao Firebase Admin SDK tu file: {abs_path}")
                    cred = credentials.Certificate(abs_path)
                    break
                    
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
