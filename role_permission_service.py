import psycopg2.extras
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

# ================= 1. QUẢN LÝ QUYỀN HẠN (PERMISSIONS) =================

def get_all_permissions():
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            SELECT PermissionID::text AS permissionid, 
                   PermissionKey AS permissionkey, 
                   Description 
            FROM Permissions 
            ORDER BY PermissionKey;
        """
        cursor.execute(sql)
        perms = cursor.fetchall()
        return True, "Lấy danh sách quyền hạn thành công", perms
    except Exception as e:
        return False, f"Lỗi truy vấn: {str(e)}", None
    finally:
        if conn: conn.close()

# ================= 2. QUẢN LÝ VAI TRÒ (ROLES) =================

def create_role(role_name, description, permission_ids=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Tạo vai trò mới
        sql_role = """
            INSERT INTO Roles (RoleName, Description) 
            VALUES (%s, %s) 
            RETURNING RoleID::text AS roleid, RoleName AS rolename, Description;
        """
        cursor.execute(sql_role, (role_name.strip(), description.strip()))
        new_role = cursor.fetchone()
        role_id = new_role['roleid']

        # Gán các quyền hạn ban đầu (nếu có)
        if permission_ids and isinstance(permission_ids, list):
            sql_perm = "INSERT INTO RolePermissions (RoleID, PermissionID) VALUES (%s, %s);"
            for perm_id in permission_ids:
                if perm_id.strip():
                    cursor.execute(sql_perm, (role_id, perm_id.strip()))

        conn.commit()
        return True, "Tạo vai trò mới và gán quyền hạn thành công!", new_role
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi tạo vai trò: {str(e)}", None
    finally:
        if conn: conn.close()

def update_role(role_id, role_name=None, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            UPDATE Roles 
            SET RoleName = COALESCE(%s, RoleName),
                Description = COALESCE(%s, Description)
            WHERE RoleID = %s
            RETURNING RoleID::text AS roleid, RoleName AS rolename, Description;
        """
        cursor.execute(sql, (role_name, description, role_id))
        updated = cursor.fetchone()
        conn.commit()
        
        if updated: return True, "Cập nhật vai trò thành công", updated
        return False, "Không tìm thấy vai trò chỉ định", None
    except InvalidTextRepresentation:
        return False, "Mã vai trò (UUID) không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def delete_role(role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor()
        
        # RÀ SOÁT RỦI RO: Kiểm tra xem có User nào đang ngậm RoleID này không
        cursor.execute("SELECT COUNT(*) FROM Users WHERE RoleID = %s;", (role_id,))
        user_count = cursor.fetchone()[0]
        if user_count > 0:
            return False, f"Không thể xóa! Đang có {user_count} tài khoản sử dụng vai trò này.", None

        # Tiến hành xóa (RolePermissions tự động bay màu nhờ ON DELETE CASCADE)
        cursor.execute("DELETE FROM Roles WHERE RoleID = %s RETURNING RoleID;", (role_id,))
        deleted = cursor.fetchone()
        conn.commit()
        
        if deleted: return True, "Xóa vai trò khỏi hệ thống thành công", None
        return False, "Vai trò không tồn tại", None
    except InvalidTextRepresentation:
        return False, "Mã vai trò không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

# ================= 3. MA TRẬN PHÂN QUYỀN TRÊN VAI TRÒ =================

def get_role_permissions(role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = """
            SELECT p.PermissionID::text AS permissionid, 
                   p.PermissionKey AS permissionkey, 
                   p.Description
            FROM RolePermissions rp
            JOIN Permissions p ON rp.PermissionID = p.PermissionID
            WHERE rp.RoleID = %s;
        """
        cursor.execute(sql, (role_id,))
        perms = cursor.fetchall()
        return True, "Lấy danh sách quyền hạn của vai trò thành công", perms
    except InvalidTextRepresentation:
        return False, "Mã vai trò không đúng định dạng", None
    except Exception as e:
        return False, str(e), None
    finally:
        if conn: conn.close()

def update_role_permissions(role_id, permission_ids):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor()
        
        # Check xem vai trò có tồn tại thật không
        cursor.execute("SELECT RoleID FROM Roles WHERE RoleID = %s;", (role_id,))
        if not cursor.fetchone():
            return False, "Vai trò không tồn tại trong hệ thống", None

        # Xóa sạch cấu hình quyền cũ của vai trò này
        cursor.execute("DELETE FROM RolePermissions WHERE RoleID = %s;", (role_id,))
        
        # Nạp mớ quyền mới vào ma trận
        if permission_ids and isinstance(permission_ids, list):
            sql_insert = "INSERT INTO RolePermissions (RoleID, PermissionID) VALUES (%s, %s);"
            for perm_id in permission_ids:
                if perm_id.strip():
                    cursor.execute(sql_insert, (role_id, perm_id.strip()))
                    
        conn.commit()
        return True, "Cập nhật ma trận phân quyền thành công!", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Thao tác phân quyền thất bại: {str(e)}", None
    finally:
        if conn: conn.close()

# ================= 4. KIỂM TRÁ QUYỀN HẠN ĐỘNG ( DÀNH CHO USER ĐĂNG NHẬP ) =================

def get_user_permissions(user_id):
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        sql = """
            SELECT p.PermissionKey 
            FROM Users u
            JOIN RolePermissions rp ON u.RoleID = rp.RoleID
            JOIN Permissions p ON rp.PermissionID = p.PermissionID
            WHERE u.UserID = %s AND u.IsActive = TRUE;
        """
        cursor.execute(sql, (user_id,))
        return [row[0] for row in cursor.fetchall()]
    except:
        return []
    finally:
        if conn: conn.close()

# ================= 5. NÂNG CẤP DÀNH RIÊNG CHO GIAO DIỆN MA TRẬN (FE MATRIX UI) =================

def get_permission_matrix():
    """Lấy dữ liệu tổng hợp cho màn hình Cấu hình phân quyền (Ma trận Toggle Switches)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Lấy danh sách toàn bộ Vai trò (Trừ Customer nếu không muốn admin sửa quyền khách, ở đây lấy hết)
        cursor.execute("SELECT RoleID::text AS role_id, RoleName AS role_name, Description FROM Roles ORDER BY RoleName;")
        roles = cursor.fetchall()
        
        # 2. Lấy danh sách toàn bộ Quyền hệ thống
        cursor.execute("SELECT PermissionID::text AS permission_id, PermissionKey AS permission_key, Description FROM Permissions ORDER BY PermissionKey;")
        permissions = cursor.fetchall()
        
        # 3. Lấy ma trận trung gian (Vai trò nào đang cầm Quyền nào)
        cursor.execute("SELECT RoleID::text AS role_id, PermissionID::text AS permission_id FROM RolePermissions;")
        mappings = cursor.fetchall()
        
        # Gom nhóm mapping theo RoleID cho FE cực kỳ dễ map vào nút gạt Toggle
        role_permissions_map = {}
        for r in roles:
            r_id = r['role_id']
            role_permissions_map[r_id] = [m['permission_id'] for m in mappings if m['role_id'] == r_id]
            
        matrix_data = {
            "roles": [dict(r) for r in roles],
            "permissions": [dict(p) for p in permissions],
            "matrix": role_permissions_map
        }
        return True, "Tải cấu hình ma trận phân quyền thành công", matrix_data
    except Exception as e:
        return False, f"Lỗi truy vấn ma trận: {str(e)}", None
    finally:
        if conn: conn.close()


def update_permission_matrix(matrix_payload):
    """
    Cập nhật đồng loạt cấu hình quyền từ nút 'Lưu cấu hình quyền'.
    Payload nhận vào là danh sách: [{'role_id': '...', 'permission_ids': ['id1', 'id2']}, ...]
    """
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor()
        
        if not isinstance(matrix_payload, list):
            return False, "Định dạng dữ liệu ma trận phải là một mảng (Array)", None

        # Chạy trong 1 Transaction duy nhất: Xóa cũ gán mới cho từng Role được gửi lên
        sql_delete = "DELETE FROM RolePermissions WHERE RoleID = %s;"
        sql_insert = "INSERT INTO RolePermissions (RoleID, PermissionID) VALUES (%s, %s);"
        
        for item in matrix_payload:
            role_id = item.get('role_id')
            perm_ids = item.get('permission_ids', [])
            
            if not role_id: continue
            
            # Xóa cấu hình cũ của Role này
            cursor.execute(sql_delete, (role_id.strip(),))
            
            # Thêm cấu hình mới
            if isinstance(perm_ids, list):
                for p_id in perm_ids:
                    if p_id and p_id.strip():
                        cursor.execute(sql_insert, (role_id.strip(), p_id.strip()))
                        
        conn.commit()
        return True, "🎉 Đã lưu toàn bộ cấu hình phân quyền mới vào hệ thống!", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cập nhật cấu hình: {str(e)}", None
    finally:
        if conn: conn.close()