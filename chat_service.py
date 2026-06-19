import psycopg2.extras
from data_manager import get_db_connection

def get_chat_history(chat_user_id, shop_id, token_user_id, role_id):
    """Lấy toàn bộ lịch sử trò chuyện được bảo mật phân quyền"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # BẢO MẬT: Nếu là Shop, kiểm tra xem có đúng là chủ Shop đang xem không
        if role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền xem tin nhắn của cửa hàng này", None

        sql = """
            SELECT 
                MessageID AS "MessageID", SenderRole AS "SenderRole",
                Content AS "Content", ImageURL AS "ImageURL", SentAt AS "SentAt"
            FROM Messages
            WHERE UserID = %s AND ShopID = %s
            ORDER BY SentAt ASC;
        """
        cursor.execute(sql, (chat_user_id, shop_id))
        messages = cursor.fetchall()
        cursor.close(); conn.close()
        
        return True, "Lấy lịch sử chat thành công", [dict(m) for m in messages]
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def send_message(chat_user_id, shop_id, sender_role, content, image_url, token_user_id, role_id):
    """Nghiệp vụ gửi tin nhắn bảo mật tuyệt đối"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # BẢO MẬT: Khách không thể mạo danh Shop, và Manager chỉ được chat cho Shop của mình
        if role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền gửi tin nhắn với tư cách cửa hàng này", None

        sql = """
            INSERT INTO Messages (UserID, ShopID, SenderRole, Content, ImageURL)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING MessageID AS "MessageID", SenderRole AS "SenderRole",
                      Content AS "Content", ImageURL AS "ImageURL", SentAt AS "SentAt";
        """
        cursor.execute(sql, (chat_user_id, shop_id, sender_role, content, image_url))
        new_msg = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        return True, "Đã gửi tin nhắn", dict(new_msg)
        
    except psycopg2.errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Khách hàng hoặc Cửa hàng không tồn tại", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None