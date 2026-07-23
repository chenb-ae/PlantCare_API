import os
import firebase_admin
from firebase_admin import credentials, firestore, auth

def initialize_firebase():
    """
    Khởi tạo Firebase Admin SDK:
    - Tìm file serviceAccountKey.json ở các đường dẫn khả thi.
    - Nếu không thấy, sử dụng Application Default Credentials (Cloud Run).
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
