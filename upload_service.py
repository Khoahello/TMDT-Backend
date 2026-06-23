import os
from werkzeug.utils import secure_filename
import time

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image(file_object):
    if not file_object or file_object.filename == '':
        return None
        
    if not allowed_file(file_object.filename):
        print(f"⚠️ [SECURITY REJECTED]: File '{file_object.filename}' không phải định dạng ảnh được phép!")
        return None
        
    try:
        # Kiểm tra dung lượng vật lý (Giới hạn bọc thép tối đa 5MB)
        file_object.seek(0, os.SEEK_END)
        if file_object.tell() > 5 * 1024 * 1024:
            print("⚠️ [SECURITY REJECTED]: Kích thước ảnh vượt quá 5MB!")
            return None
        file_object.seek(0, 0) # Trả con trỏ về đầu để lưu

        safe_filename = secure_filename(file_object.filename)
        unique_filename = f"{int(time.time())}_{safe_filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        file_object.save(file_path)
        file_url = f"/{UPLOAD_FOLDER}/{unique_filename}".replace("\\", "/")
        return file_url
        
    except Exception as e:
        print(f"❌ [UPLOAD FAILED]: {str(e)}")
        return None