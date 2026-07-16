import os
import psycopg2
from psycopg2 import pool
import psycopg2.extras

# Khởi tạo Hồ chứa kết nối (Connection Pool) dùng chung cho toàn hệ thống
# Min = 1, Max = 20 kết nối đồng thời.
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


class PooledConnectionWrapper:
    """
    Lớp bọc (Wrapper) an toàn cho Connection C-Extension.
    Nhiệm vụ: Canh gác lệnh close() để trả về hồ chứa thay vì đóng hẳn.
    """
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def close(self):
        """Đánh chặn lệnh close() từ tầng Service để trả về Pool"""
        if self._conn:
            try:
                self._pool.putconn(self._conn)
            except Exception as e:
                print(f"⚠️ [POOL WARNING]: Không thể trả kết nối về hồ - {e}")
            finally:
                self._conn = None

    def __getattr__(self, name):
        """
        Ủy quyền (Delegate) tự động.
        Bất kỳ lệnh nào khác (cursor, commit, rollback...) đều được chuyển thẳng cho conn gốc.
        """
        return getattr(self._conn, name)


def get_db_connection():
    """Nhà máy cấp phát kết nối siêu tốc lấy từ Pool."""
    if not db_pool:
        print("❌ [DB_ERROR]: Hồ chứa kết nối chưa sẵn sàng!")
        return None

    try:
        # Rút 1 kết nối gốc từ trong Hồ ra
        raw_conn = db_pool.getconn()
        
        if raw_conn:
            # Bọc nó vào áo khoác Python rồi mới ném lên cho tầng Service sử dụng
            return PooledConnectionWrapper(db_pool, raw_conn)
            
    except Exception as e:
        print(f"❌ [DB_CONNECTION_FAILED]: Cạn kiệt kết nối hoặc lỗi mạng - {e}")
        return None