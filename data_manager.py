import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Tự động tìm và đọc nội dung file .env
load_dotenv()

# Lấy thông tin từ file .env gán vào biến
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

def get_db_connection():
    """Hàm khởi tạo đường ống kết nối đến PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f" Lỗi kết nối Database: {e}")
        return None

# Đoạn test nhanh: Chỉ chạy khi bấm run trực tiếp file này
if __name__ == "__main__":
    print("⏳ Đang thử kết nối...")
    test_conn = get_db_connection()
    if test_conn:
        print(" Tuyệt vời! Kết nối Database thành công!")
        cursor = test_conn.cursor()
        cursor.execute("SELECT version();")
        print(f" Phiên bản DB: {cursor.fetchone()[0]}")
        cursor.close()
        test_conn.close()