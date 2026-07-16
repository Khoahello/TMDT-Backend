import os
import psycopg2
from psycopg2 import pool
import psycopg2.extras

# Từ điển lưu trữ Pool theo mã Tiến trình (PID) của Gunicorn
# Đảm bảo các Worker không bao giờ đánh nhau giành kết nối
_pools = {}

def get_pool():
    """Tự động cấp phát Pool riêng cho từng Worker dựa vào PID"""
    pid = os.getpid()
    if pid not in _pools:
        try:
            # Mỗi worker chỉ cần 1-5 kết nối là gánh dư sức hàng ngàn request
            _pools[pid] = psycopg2.pool.ThreadedConnectionPool(
                1, 5, 
                host=os.getenv("DB_HOST"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=os.getenv("DB_PORT", "5432")
            )
            print(f"✅ [SYSTEM]: Đã tạo Connection Pool an toàn cho Worker PID: {pid}")
        except Exception as e:
            print(f"❌ [CRITICAL FATAL]: Lỗi tạo Pool cho PID {pid} - {e}")
            return None
    return _pools[pid]


class PooledConnectionWrapper:
    """Lớp bọc chặn lệnh close() để đưa kết nối về đúng Hồ chứa"""
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn

    def close(self):
        """Dọn dẹp rác giao dịch và trả kết nối về Pool"""
        if self._conn:
            try:
                # ⚡️ BỌC THÉP: Xóa sạch các Transaction đang treo trước khi trả về hồ
                if not self._conn.closed:
                    self._conn.rollback()
                self._pool.putconn(self._conn)
            except Exception as e:
                print(f"⚠️ [POOL WARNING]: Không thể trả kết nối về hồ - {e}")
            finally:
                self._conn = None

    def __getattr__(self, name):
        """Cho phép gọi mọi lệnh bình thường (cursor, commit...) trỏ xuống conn gốc"""
        return getattr(self._conn, name)


def get_db_connection():
    """Hàm lấy kết nối được bảo vệ hoàn toàn khỏi lỗi Timeout Gunicorn"""
    current_pool = get_pool()
    if not current_pool:
        return None

    try:
        raw_conn = current_pool.getconn()
        if raw_conn:
            return PooledConnectionWrapper(current_pool, raw_conn)
    except Exception as e:
        print(f"❌ [DB_CONNECTION_FAILED]: {e}")
        return None