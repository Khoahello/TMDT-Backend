import psycopg2.extras
import math
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

def _get_role_uuid(conn, role_name):
    """Hàm nội bộ: Truy vấn động CSDL bốc Khóa UUID của một Role theo Tên"""
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID FROM Roles WHERE RoleName = %s", (role_name,))
    res = cursor.fetchone()
    cursor.close()
    if not res:
        raise ValueError(f"CRITICAL ERROR: Không tìm thấy Role '{role_name}' trong CSDL!")
    return str(res[0])

# Trong file shops_service.py, sửa đè 2 hàm GET này:

def get_all_shops(page=1, limit=10, role_name=None):
    """Admin soi Full danh sách, Khách soi chỉ thấy Shop IsActive=True"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        where_clause = "" if role_name == 'Admin' else "WHERE IsActive = TRUE"

        cursor.execute(f"SELECT COUNT(*) FROM Shops {where_clause};")
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        data_query = f"""
            SELECT 
                ShopID::text AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                Hotline AS "Hotline", Description AS "Description", Rating AS "Rating",
                ShopImageURL AS "ShopImageURL", ManagerID::text AS "ManagerID", 
                IsActive AS "IsActive", CreatedAt AS "CreatedAt"
            FROM Shops
            {where_clause}
            ORDER BY CreatedAt DESC, ShopID ASC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(data_query, (limit, offset))
        shops_list = cursor.fetchall()
        
        for s in shops_list:
            if s.get('Rating') is not None:
                s['Rating'] = float(s['Rating'])
                
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        pagination_result = {
            "shops": shops_list,
            "meta": { "total_items": total_items, "current_page": page, "total_pages": total_pages }
        }
        return True, "Lấy danh sách cửa hàng thành công", pagination_result
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()
    
def get_shop_details(shop_id, role_name=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        active_filter = "" if role_name == 'Admin' else "AND IsActive = TRUE"

        sql_query = f"""
            SELECT 
                ShopID::text AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                Hotline AS "Hotline", Description AS "Description", Rating AS "Rating",
                ShopImageURL AS "ShopImageURL", ManagerID::text AS "ManagerID", 
                IsActive AS "IsActive", CreatedAt AS "CreatedAt", UpdatedAt AS "UpdatedAt"
            FROM Shops WHERE ShopID = %s {active_filter};
        """
        cursor.execute(sql_query, (shop_id,))
        shop = cursor.fetchone()
        
        if shop:
            if shop.get('Rating') is not None: shop['Rating'] = float(shop['Rating'])
            return True, "Lấy thông tin chi tiết cửa hàng thành công", shop
        return False, "Không tìm thấy cửa hàng hoặc cửa hàng đang tạm đóng cửa", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ShopID định danh không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()
    
def create_shop(shop_name, address, hotline, manager_id, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        # 1. TRUY VẤN ĐỘNG: Bốc Khóa UUID của Manager và Customer ra dùng
        manager_role_uuid = _get_role_uuid(conn, 'Manager')
        customer_role_uuid = _get_role_uuid(conn, 'Customer')

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        sql_insert_shop = """
            INSERT INTO Shops (ShopName, Address, Hotline, ManagerID, Description) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING ShopID::text AS "ShopID", ShopName AS "ShopName", Description AS "Description", Rating AS "Rating";
        """
        cursor.execute(sql_insert_shop, (shop_name, address, hotline, str(manager_id), description))
        new_shop = cursor.fetchone()
        
        if new_shop.get('Rating') is not None: new_shop['Rating'] = float(new_shop['Rating'])
        
        # 2. PHÂN QUYỀN ĐỘNG: Nạp Khóa Manager UUID vào User
        sql_update_role = """
            UPDATE Users 
            SET RoleID = %s, UpdatedAt = CURRENT_TIMESTAMP 
            WHERE UserID = %s AND RoleID = %s;
        """
        cursor.execute(sql_update_role, (manager_role_uuid, str(manager_id), customer_role_uuid))
        conn.commit()
        
        # Trả về gói dữ liệu bọc thép cho Router nạp Token
        return True, "Tạo cửa hàng và phân quyền thành công", {
            "shop": new_shop,
            "manager_role_uuid": manager_role_uuid
        }
    except psycopg2.errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Mã tài khoản người quản lý không tồn tại", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()
    
def update_shop(shop_id, user_id, role_name, shop_name=None, address=None, hotline=None, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (shop_id,))
        shop = cursor.fetchone()
        
        if not shop: return False, "Không tìm thấy cửa hàng", None
            
        # SO QUYỀN BẰNG TÊN: role_name != 'Admin'
        if str(shop['managerid']) != str(user_id) and role_name != 'Admin':
            return False, "Bạn không có quyền cập nhật thông tin cửa hàng này", None

        sql_query = """
            UPDATE Shops 
            SET ShopName = COALESCE(%s, ShopName), Address = COALESCE(%s, Address),
                Hotline = COALESCE(%s, Hotline), Description = COALESCE(%s, Description),
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE ShopID = %s AND IsActive = TRUE
            RETURNING ShopID::text AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                      Hotline AS "Hotline", Description AS "Description", Rating AS "Rating", ManagerID::text AS "ManagerID";
        """
        cursor.execute(sql_query, (shop_name, address, hotline, description, shop_id))
        updated_shop = cursor.fetchone()
        conn.commit()
        
        if updated_shop:
            if updated_shop.get('Rating') is not None: updated_shop['Rating'] = float(updated_shop['Rating'])
            return True, "Cập nhật thông tin cửa hàng thành công", updated_shop
        return False, "Cửa hàng đã ngừng hoạt động", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ShopID định danh không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def toggle_shop_status(shop_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Shops SET IsActive = NOT IsActive, UpdatedAt = CURRENT_TIMESTAMP WHERE ShopID = %s
            RETURNING ShopID::text AS "ShopID", ShopName AS "ShopName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (shop_id,))
        updated_shop = cursor.fetchone()
        conn.commit()
        
        if updated_shop:
            trang_thai = "Mở cửa hoạt động" if updated_shop["IsActive"] else "Đóng cửa tạm nghỉ"
            return True, f"Đã chuyển trạng thái cửa hàng sang: {trang_thai}", updated_shop
        return False, "Không tìm thấy cửa hàng", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ShopID không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()