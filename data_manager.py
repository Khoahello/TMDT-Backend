import os
import psycopg2
import psycopg2.extras

# Biến lưu kết nối đứng yên một chỗ
_global_connection = None

def get_db_connection():
    """Hàm trả về 1 đường ống kết nối duy nhất, đứt thì tự nối lại"""
    global _global_connection
    try:
        # Nếu chưa có kết nối, hoặc kết nối đã bị đứt ngang -> Mở 1 lần duy nhất!
        if _global_connection is None or _global_connection.closed != 0:
            _global_connection = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=os.getenv("DB_PORT", "5432")
            )
            # TỰ ĐỘNG LƯU: Cứ có lệnh INSERT/UPDATE là chốt đĩa cứng luôn, không sợ quên commit!
            _global_connection.autocommit = True 

        return _global_connection
    except Exception as e:
        print(f"❌ Lỗi đường ống DB Singleton: {e}")
        return None