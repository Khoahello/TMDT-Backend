import os
import psycopg2
import psycopg2.extras

def get_db_connection():
    """Nhà máy cấp phát kết nối CSDL độc lập. Tôn trọng tuyệt đối chuẩn ACID và lệnh conn.close()"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"❌ [DB_CONNECTION_FAILED]: {e}")
        return None