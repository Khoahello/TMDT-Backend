import psycopg2.extras
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

def get_chat_history(chat_user_id, shop_id, token_user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # [SO QUYỀN ĐỘNG]: role_name == 'Manager'
        if role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                return False, "Bạn không có quyền xem tin nhắn của cửa hàng này", None

        # [CHUẨN JSON]: Ép MessageID::text, UserID::text, ShopID::text
        sql = """
            SELECT 
                MessageID::text AS "MessageID", UserID::text AS "UserID", ShopID::text AS "ShopID",
                SenderRole AS "SenderRole", Content AS "Content", ImageURL AS "ImageURL", SentAt AS "SentAt"
            FROM Messages
            WHERE UserID = %s AND ShopID = %s
            ORDER BY SentAt ASC;
        """
        cursor.execute(sql, (chat_user_id, shop_id))
        messages = cursor.fetchall()
        return True, "Lấy lịch sử chat thành công", [dict(m) for m in messages]
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID định danh người dùng hoặc Cửa hàng không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def send_message(chat_user_id, shop_id, sender_role, content, image_url, token_user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                return False, "Bạn không có quyền gửi tin nhắn đại diện cho cửa hàng này", None

        # [CHUẨN JSON]: Ép MessageID::text
        sql = """
            INSERT INTO Messages (UserID, ShopID, SenderRole, Content, ImageURL)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING MessageID::text AS "MessageID", UserID::text AS "UserID", ShopID::text AS "ShopID",
                      SenderRole AS "SenderRole", Content AS "Content", ImageURL AS "ImageURL", SentAt AS "SentAt";
        """
        cursor.execute(sql, (chat_user_id, shop_id, sender_role, content, image_url))
        new_msg = cursor.fetchone()
        conn.commit()
        return True, "Đã gửi tin nhắn", dict(new_msg)
        
    except psycopg2.errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Khách hàng hoặc Cửa hàng không tồn tại trong hệ thống", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()