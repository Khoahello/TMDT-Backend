import os
import cloudinary
import cloudinary.uploader
from werkzeug.utils import secure_filename

# ================= CẤU HÌNH CLOUDINARY =================
# Tự động nhặt chìa khóa từ Render Environment
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
    Nhận file từ Request, kiểm tra an ninh và đẩy thẳng lên Cloudinary.
    """
    if not file_object or file_object.filename == '':
        return None
        
    if not allowed_file(file_object.filename):
        print(f"⚠️ [SECURITY REJECTED]: File '{file_object.filename}' không phải định dạng ảnh được phép!")
        return None
        
    try:
        # 1. KIỂM TRA DUNG LƯỢNG (Giữ nguyên chốt chặn 5MB cực xịn của ông)
        file_object.seek(0, os.SEEK_END)
        if file_object.tell() > 5 * 1024 * 1024:
            print("⚠️ [SECURITY REJECTED]: Kích thước ảnh vượt quá 5MB!")
            return None
        file_object.seek(0, 0) # Trả con trỏ về đầu để chuẩn bị gửi đi

        # Lọc tên file an toàn trước khi đẩy lên mây
        safe_filename = secure_filename(file_object.filename).rsplit('.', 1)[0]

        # 2. BẮN HỎA TIỄN LÊN CLOUDINARY
        upload_result = cloudinary.uploader.upload(
            file_object,
            folder="tmdt_due_uploads", # Gom hết vào thư mục này trên Cloudinary cho gọn gàng
            public_id=safe_filename,   # Đặt tên file trên Cloud
            resource_type="image"
        )
        
        # 3. NHẬN KẾT QUẢ VỀ
        # Lấy link HTTPS bảo mật tuyệt đối
        file_url = upload_result.get('secure_url')
        print(f"✅ [UPLOAD SUCCESS]: {file_url}")
        
        return file_url
        
    except Exception as e:
        print(f"❌ [CLOUDINARY FAILED]: Lỗi tải ảnh lên Cloud - {str(e)}")
        return None