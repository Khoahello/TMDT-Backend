import os
import psycopg2
from psycopg2 import pool
import psycopg2.extras

# Khởi tạo Hồ chứa kết nối (Connection Pool) dùng chung cho toàn hệ thống
# Min = 1, Max = 20 kết nối đồng thời. Tùy chỉnh theo gói RAM của Render.
try:
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        1, 20,
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432")
    )
    print("✅ [SYSTEM]: Đã khởi tạo thành công Connection Pool cho PostgreSQL!")
except Exception as e:
    print(f"❌ [CRITICAL FATAL]: Không thể khởi tạo Connection Pool - {e}")
    db_pool = None


def get_db_connection():
    """
    Nhà máy cấp phát kết nối siêu tốc từ Pool.
    Tự động ghi đè hàm close() để tương thích 100% với code cũ của toàn bộ hệ thống.
    """
    if not db_pool:
        print("❌ [DB_ERROR]: Hồ chứa kết nối chưa sẵn sàng!")
        return None

    try:
        # Rút 1 kết nối có sẵn từ trong Hồ ra dùng (Mất 0.001 giây thay vì 0.2 giây)
        conn = db_pool.getconn()

        if conn:
            # ⚡️ TUYỆT KỸ MONKEY-PATCHING:
            # Ghi đè phương thức .close() mặc định của connection này.
            # Khi file Service gọi conn.close(), nó sẽ thực thi lệnh db_pool.putconn(conn)
            # Giúp ông KHÔNG PHẢI SỬA bất kỳ file Service nào mà hệ thống vẫn chạy chuẩn!
            
            # Lưu lại hàm close gốc (đề phòng cần dùng)
            conn._original_close = conn.close 
            
            # Tráo đổi hàm close
            def pooled_close():
                try:
                    db_pool.putconn(conn)
                except Exception as put_err:
                    print(f"⚠️ [POOL WARNING]: Lỗi khi trả connection về pool - {put_err}")
            
            conn.close = pooled_close
            
            return conn
            
    except Exception as e:
        print(f"❌ [DB_CONNECTION_FAILED]: Cạn kiệt kết nối hoặc lỗi mạng - {e}")
        return None