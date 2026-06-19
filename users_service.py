import psycopg2.extras
import math
from data_manager import get_db_connection

# ================= MODULE ROLES =================
def get_all_roles():
    """Lấy danh sách tất cả các vai trò (Admin, Manager, Customer)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT RoleID AS "RoleID", RoleName AS "RoleName" FROM Roles ORDER BY RoleID;')
        roles = cursor.fetchall()
        cursor.close(); conn.close()
        return True, "Lấy danh sách vai trò thành công", roles
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def assign_role(user_id, role_id):
    """Cập nhật quyền (Role) cho User"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Check xem RoleID có tồn tại không và lấy luôn cái Tên Role
        cursor.execute('SELECT RoleName FROM Roles WHERE RoleID = %s;', (role_id,))
        role = cursor.fetchone()
        if not role:
            cursor.close(); conn.close()
            return False, "Vai trò không hợp lệ", None

        sql = """
            UPDATE Users SET RoleID = %s, UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s RETURNING UserID::text;
        """
        cursor.execute(sql, (role_id, user_id))
        updated_user = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()

        if updated_user:
            return True, "Cập nhật vai trò người dùng thành công", {"RoleID": role_id, "RoleName": role['rolename']}
        return False, "Không tìm thấy người dùng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

# ================= MODULE USERS =================
def get_all_users(page=1, limit=10):
    """Lấy danh sách người dùng có phân trang (JOIN với Roles để lấy RoleName)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) FROM Users;")
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        sql = """
            SELECT u.UserID::text AS "UserID", u.FullName AS "FullName", u.Email AS "Email", 
                   u.PhoneNumber AS "PhoneNumber", u.AvatarURL AS "AvatarURL", 
                   u.RoleID AS "RoleID", r.RoleName AS "RoleName", u.IsActive AS "IsActive"
            FROM Users u JOIN Roles r ON u.RoleID = r.RoleID
            ORDER BY u.CreatedAt DESC LIMIT %s OFFSET %s;
        """
        cursor.execute(sql, (limit, offset))
        users = cursor.fetchall()
        cursor.close(); conn.close()
        
        return True, "Lấy danh sách người dùng thành công", {
            "users": users,
            "meta": {"total_items": total_items, "current_page": page, "total_pages": math.ceil(total_items/limit) if total_items>0 else 1}
        }
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_user_profile(user_id):
    """Lấy hồ sơ cá nhân của 1 user"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            SELECT u.UserID::text AS "UserID", u.FullName AS "FullName", u.Email AS "Email", 
                   u.PhoneNumber AS "PhoneNumber", u.Address AS "Address", u.AvatarURL AS "AvatarURL", r.RoleName AS "RoleName"
            FROM Users u JOIN Roles r ON u.RoleID = r.RoleID WHERE u.UserID = %s;
        """
        cursor.execute(sql, (user_id,))
        user = cursor.fetchone()
        cursor.close(); conn.close()
        
        if user: return True, "Lấy thông tin cá nhân thành công", dict(user)
        return False, "Không tìm thấy người dùng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def update_profile(user_id, full_name=None, address=None, avatar_url=None):
    """Cập nhật Tên, Địa chỉ và Ảnh đại diện (Dùng COALESCE để không bắt buộc nhập tất cả)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            UPDATE Users 
            SET FullName = COALESCE(%s, FullName), 
                Address = COALESCE(%s, Address), 
                AvatarURL = COALESCE(%s, AvatarURL),
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE UserID = %s AND IsActive = TRUE
            RETURNING FullName AS "FullName", Address AS "Address", AvatarURL AS "AvatarURL", UpdatedAt AS "UpdatedAt";
        """
        cursor.execute(sql, (full_name, address, avatar_url, user_id))
        updated = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated: return True, "Cập nhật hồ sơ thành công", dict(updated)
        return False, "Không tìm thấy người dùng hoặc tài khoản bị khóa", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def toggle_user_status(user_id):
    """Bật/Tắt trạng thái hoạt động của User (Khóa tài khoản)"""
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
        cursor.close(); conn.close()
        
        if user:
            msg = "Đã mở khóa tài khoản" if user['IsActive'] else "Đã khóa tài khoản người dùng thành công"
            return True, msg, {"IsActive": user['IsActive'], "UpdatedAt": user['UpdatedAt']}
        return False, "Không tìm thấy người dùng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None