import psycopg2.extras
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

def get_chat_history(chat_user_id, shop_id, token_user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                return False, "Bạn không có quyền xem tin nhắn của cửa hàng này", None

        # [VÁ LỖ HỔNG DATETIME]: Ép SentAt::text để JSON và SocketIO không bị sập
        sql = """
            SELECT 
                MessageID::text AS "MessageID", UserID::text AS "UserID", ShopID::text AS "ShopID",
                SenderRole AS "SenderRole", Content AS "Content", ImageURL AS "ImageURL", SentAt::text AS "SentAt"
            FROM Messages
            WHERE UserID = %s AND ShopID = %s
            ORDER BY SentAt ASC;
        """
        cursor.execute(sql, (chat_user_id, shop_id))
        messages = cursor.fetchall()
        return True, "Lấy lịch sử chat thành công", [dict(m) for m in messages]
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID định danh không hợp lệ", None
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

        # [VÁ LỖ HỔNG DATETIME]: Ép SentAt::text ngay từ lệnh RETURNING
        sql = """
            INSERT INTO Messages (UserID, ShopID, SenderRole, Content, ImageURL)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING MessageID::text AS "MessageID", UserID::text AS "UserID", ShopID::text AS "ShopID",
                      SenderRole AS "SenderRole", Content AS "Content", ImageURL AS "ImageURL", SentAt::text AS "SentAt";
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

# ================= NGHIỆP VỤ BỔ SUNG: LẤY DANH SÁCH HỘI THOẠI (INBOX ROOMS) =================

def get_conversations(token_user_id, role_name, shop_id_param=None):
    """Lấy danh sách các cuộc hội thoại (Cột bên trái của Messenger)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_name == 'Customer':
            # Khách hàng xem danh sách các Shop mình từng nhắn
            sql = """
                SELECT DISTINCT ON (m.ShopID) 
                       m.ShopID::text AS shop_id, s.ShopName AS shop_name, s.ShopImageURL AS shop_image,
                       m.Content AS last_message, m.SentAt::text AS last_sent, m.SenderRole AS last_sender
                FROM Messages m
                JOIN Shops s ON m.ShopID = s.ShopID
                WHERE m.UserID = %s
                ORDER BY m.ShopID, m.SentAt DESC;
            """
            cursor.execute(sql, (token_user_id,))
            rooms = cursor.fetchall()
            # Sắp xếp lại theo thời gian tin nhắn mới nhất lên đầu
            rooms.sort(key=lambda x: x['last_sent'], reverse=True)
            return True, "Lấy danh sách hội thoại thành công", [dict(r) for r in rooms]

        elif role_name == 'Manager':
            if not shop_id_param:
                return False, "Chủ shop cần truyền tham số shop_id để xem hộp thư", None
                
            # Xác thực chủ shop
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (shop_id_param,))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(token_user_id):
                return False, "Bạn không có quyền quản lý hộp thư của cửa hàng này", None

            # Chủ shop xem danh sách Khách hàng từng nhắn cho Shop
            sql = """
                SELECT DISTINCT ON (m.UserID) 
                       m.UserID::text AS user_id, u.FullName AS user_name, u.AvatarURL AS user_avatar,
                       m.Content AS last_message, m.SentAt::text AS last_sent, m.SenderRole AS last_sender
                FROM Messages m
                JOIN Users u ON m.UserID = u.UserID
                WHERE m.ShopID = %s
                ORDER BY m.UserID, m.SentAt DESC;
            """
            cursor.execute(sql, (shop_id_param,))
            rooms = cursor.fetchall()
            rooms.sort(key=lambda x: x['last_sent'], reverse=True)
            return True, "Lấy danh sách khách hàng liên hệ thành công", [dict(r) for r in rooms]
            
        return False, "Vai trò không hỗ trợ xem hộp thư", None
    except Exception as e:
        return False, str(e), None
    finally:
        if conn: conn.close()