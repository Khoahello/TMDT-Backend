import psycopg2.extras
import math
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

# ================= MODULE ROLES =================
def get_all_roles():
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Ép tường minh RoleID::text để JSON không hộc máu
        cursor.execute('SELECT RoleID::text AS "RoleID", RoleName AS "RoleName" FROM Roles ORDER BY "RoleName";')
        roles = cursor.fetchall()
        return True, "Lấy danh sách vai trò thành công", roles
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi truy vấn SQL: {str(e)}", None
    finally:
        if conn: conn.close()

def assign_role(user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT RoleName FROM Roles WHERE RoleID = %s;', (role_id,))
        role = cursor.fetchone()
        if not role:
            return False, "Vai trò không hợp lệ (Mã RoleID không tồn tại trong DB)", None

        sql = """
            UPDATE Users SET RoleID = %s, UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s RETURNING UserID::text;
        """
        cursor.execute(sql, (role_id, user_id))
        updated_user = cursor.fetchone()
        conn.commit()

        if updated_user:
            return True, "Cập nhật vai trò người dùng thành công", {"RoleID": str(role_id), "RoleName": role['rolename']}
        return False, "Không tìm thấy người dùng trong hệ thống", None
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã định danh (UUID) không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cập nhật SQL: {str(e)}", None
    finally:
        if conn: conn.close()

# ================= MODULE USERS =================
def get_all_users(page=1, limit=10):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) FROM Users;")
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        # Ép chuẩn u.UserID::text và u.RoleID::text
        sql = """
            SELECT u.UserID::text AS "UserID", u.FullName AS "FullName", u.Email AS "Email", 
                   u.PhoneNumber AS "PhoneNumber", u.AvatarURL AS "AvatarURL", 
                   u.RoleID::text AS "RoleID", r.RoleName AS "RoleName", u.IsActive AS "IsActive"
            FROM Users u JOIN Roles r ON u.RoleID = r.RoleID
            ORDER BY u.CreatedAt DESC LIMIT %s OFFSET %s;
        """
        cursor.execute(sql, (limit, offset))
        users = cursor.fetchall()
        
        return True, "Lấy danh sách người dùng thành công", {
            "users": users,
            "meta": {"total_items": total_items, "current_page": page, "total_pages": math.ceil(total_items/limit) if total_items > 0 else 1}
        }
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi truy vấn SQL: {str(e)}", None
    finally:
        if conn: conn.close()

def get_user_profile(user_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Bổ sung Gender và ép kiểu Birthday sang chuỗi YYYY-MM-DD để JSON không lỗi
        sql = """
            SELECT u.UserID::text AS "UserID", u.FullName AS "FullName", u.Email AS "Email", 
                   u.PhoneNumber AS "PhoneNumber", u.Address AS "Address", u.AvatarURL AS "AvatarURL", 
                   u.Gender AS "Gender", TO_CHAR(u.Birthday, 'YYYY-MM-DD') AS "Birthday",
                   u.RoleID::text AS "RoleID", r.RoleName AS "RoleName"
            FROM Users u JOIN Roles r ON u.RoleID = r.RoleID WHERE u.UserID = %s;
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
        
        if user: return True, "Lấy thông tin cá nhân thành công", dict(user)
        return False, "Không tìm thấy hồ sơ người dùng", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã UserID không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def update_profile(user_id, full_name=None, phone=None, address=None, gender=None, birthday=None, avatar_url=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Nạp đủ bộ 6 tham số vào lệnh UPDATE
        sql = """
            UPDATE Users 
            SET FullName = COALESCE(%s, FullName), 
                PhoneNumber = COALESCE(%s, PhoneNumber),
                Address = COALESCE(%s, Address), 
                Gender = COALESCE(%s, Gender),
                Birthday = COALESCE(%s::DATE, Birthday),
                AvatarURL = COALESCE(%s, AvatarURL),
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s AND IsActive = TRUE
            RETURNING FullName AS "FullName", PhoneNumber AS "PhoneNumber", Address AS "Address", 
                      Gender AS "Gender", TO_CHAR(Birthday, 'YYYY-MM-DD') AS "Birthday", 
                      AvatarURL AS "AvatarURL", UpdatedAt AS "UpdatedAt";
        """
        cursor.execute(sql, (full_name, phone, address, gender, birthday, avatar_url, user_id))
        updated = cursor.fetchone()
        conn.commit()
        
        if updated: return True, "Cập nhật hồ sơ thành công", dict(updated)
        return False, "Không tìm thấy người dùng hoặc tài khoản đang bị khóa", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã định danh không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def toggle_user_status(user_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            UPDATE Users SET IsActive = NOT IsActive, UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s RETURNING UserID::text, IsActive AS "IsActive", UpdatedAt AS "UpdatedAt";
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
        conn.commit()
        
        if user:
            msg = "Đã mở khóa tài khoản" if user['IsActive'] else "Đã khóa tài khoản người dùng thành công"
            return True, msg, {"IsActive": user['IsActive'], "UpdatedAt": user['UpdatedAt']}
        return False, "Không tìm thấy người dùng", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã UserID không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()