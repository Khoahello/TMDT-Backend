import os
from werkzeug.utils import secure_filename
import time

# Cấu hình thư mục lưu ảnh tạm trên máy Local (Máy tính của ông)
# Nó sẽ tự động tạo thư mục 'static/uploads' ngang hàng với app.py nếu chưa có
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def upload_image(file_object):
    """
    Hàm xử lý file ảnh. 
    HIỆN TẠI: Lưu tạm vào ổ cứng máy tính.
    TƯƠNG LAI: Sẽ xóa code lưu Local đi và thay bằng 2 dòng code gọi API Cloudinary.
    """
    # Nếu không có file gửi lên, trả về None để DB tự hiểu là không cập nhật ảnh
    if not file_object or file_object.filename == '':
        return None
        
    try:
        # 1. Bảo mật tên file (xóa các ký tự tiếng Việt có dấu, khoảng trắng, ký tự lạ)
        # Ví dụ: "Ảnh Sản Phẩm.jpg" -> "Anh_San_Pham.jpg"
        safe_filename = secure_filename(file_object.filename)
        
        # 2. Gắn thêm mốc thời gian vào tên file để chống trùng lặp
        # Ví dụ 2 khách cùng up file tên "avatar.png" thì không bị ghi đè lên nhau
        unique_filename = f"{int(time.time())}_{safe_filename}"
        
        # 3. Tạo đường dẫn tuyệt đối để lưu vào máy tính
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # 4. Thực hiện lệnh lưu file vật lý vào ổ cứng
        file_object.save(file_path)
        
        # 5. Trả về cái đường dẫn ảo (URL) để lưu vào bảng Database
        # Thay vì trả link Cloudinary, tạm thời trả về link thư mục Local
        # Dùng replace để đảm bảo định dạng dấu '/' chuẩn trên cả Windows và Mac
        file_url = f"/{UPLOAD_FOLDER}/{unique_filename}".replace("\\", "/")
        
        return file_url
        
    except Exception as e:
        print("❌ Lỗi khi lưu file:", str(e))
        return None