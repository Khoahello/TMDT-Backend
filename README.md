Hãy làm theo các bước sau để chạy server trên máy cá nhân nhé:

1. Setup Database:

Mở pgAdmin, tạo database tên là TMDT.

Chạy file TMDT.sql để tạo bảng, sau đó chạy TMDT_data.sql để có dữ liệu mẫu.

2. Cài đặt môi trường:

Mở Terminal tại thư mục code, gõ lệnh: pip install -r requirements.txt

3. Cấu hình biến môi trường (Quan trọng):

Copy file .env.example và đổi tên nó thành .env.

Mở file .env lên, sửa lại DB_PASSWORD cho đúng với mật khẩu pgAdmin trên máy của
mọi người.

4. Chạy Server và Test:

Gõ lệnh: python app.py (Server sẽ chạy ở cổng 5000).

Import file TMDT_API_Mock.postman_collection.json vào Postman.

Lưu ý test API: Hãy gọi API Login trước để lấy Token, sau đó qua tab
Authorization -> chọn Bearer Token -> dán token vào để test các API khác nhé! FE
cứ dựa vào Postman này để ráp giao diện nha.
