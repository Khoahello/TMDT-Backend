import os
import cloudinary
import cloudinary.uploader
import base64
from werkzeug.utils import secure_filename

# ================= CẤU HÌNH CLOUDINARY =================
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True # Ép buộc dùng HTTPS
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image(file_object):
    """
    Nhận file từ Request, chuyển sang chuỗi Base64 để tránh lỗi đệ quy,
    sau đó đẩy thẳng lên mây Cloudinary.
    """
    if not file_object or file_object.filename == '':
        return None
        
    if not allowed_file(file_object.filename):
        print(f"⚠️ [SECURITY REJECTED]: File '{file_object.filename}' không phải định dạng ảnh được phép!")
        return None
        
    try:
        # 1. KIỂM TRA DUNG LƯỢNG (Chốt chặn 5MB)
        file_object.seek(0, os.SEEK_END)
        if file_object.tell() > 5 * 1024 * 1024:
            print("⚠️ [SECURITY REJECTED]: Kích thước ảnh vượt quá 5MB!")
            return None
        file_object.seek(0, 0) # Trả con trỏ về đầu

        # 2. XỬ LÝ TÊN FILE AN TOÀN
        safe_filename = secure_filename(file_object.filename)
        if '.' in safe_filename:
            safe_filename = safe_filename.rsplit('.', 1)[0]
        # Xử lý trường hợp file tên tiếng việt bị secure_filename xóa trắng
        if not safe_filename:
            safe_filename = "tmdt_image"

        # 3. ⚡️ TUYỆT KỸ TRÁNH LỖI ĐỆ QUY (RECURSION ERROR) ⚡️
        # Chuyển đổi dữ liệu file thô thành chuỗi Base64 Data URI
        file_bytes = file_object.read()
        encoded_string = base64.b64encode(file_bytes).decode('utf-8')
        mime_type = file_object.mimetype or 'image/jpeg'
        
        data_uri = f"data:{mime_type};base64,{encoded_string}"

        # 4. BẮN HỎA TIỄN LÊN CLOUDINARY
        upload_result = cloudinary.uploader.upload(
            data_uri,                  # Gửi chuỗi string thay vì object file
            folder="tmdt_due_uploads", 
            public_id=safe_filename,   
            resource_type="auto"       # Tự động nhận diện ảnh
        )
        
        # 5. Lấy link trả về
        file_url = upload_result.get('secure_url')
        print(f"✅ [UPLOAD SUCCESS]: {file_url}")
        
        return file_url
        
    except Exception as e:
        print(f"❌ [CLOUDINARY FAILED]: {str(e)}")
        return None