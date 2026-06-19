import psycopg2.extras
import math
from data_manager import get_db_connection

def get_all_shops(page=1, limit=10):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) FROM Shops WHERE IsActive = TRUE;")
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        # ĐÃ BỔ SUNG Description và Rating
        data_query = """
            SELECT 
                ShopID AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                Hotline AS "Hotline", Description AS "Description", Rating AS "Rating",
                ShopImageURL AS "ShopImageURL", ManagerID AS "ManagerID", 
                IsActive AS "IsActive", CreatedAt AS "CreatedAt"
            FROM Shops
            WHERE IsActive = TRUE
            ORDER BY CreatedAt DESC, "ShopID" ASC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(data_query, (limit, offset))
        shops_list = cursor.fetchall()
        cursor.close(); conn.close()
        
        # Xử lý ép kiểu Decimal sang Float cho Rating tránh lỗi
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
    
def get_shop_details(shop_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # ĐÃ BỔ SUNG Description và Rating
        sql_query = """
            SELECT 
                ShopID AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                Hotline AS "Hotline", Description AS "Description", Rating AS "Rating",
                ShopImageURL AS "ShopImageURL", ManagerID AS "ManagerID", 
                IsActive AS "IsActive", CreatedAt AS "CreatedAt", UpdatedAt AS "UpdatedAt"
            FROM Shops WHERE ShopID = %s AND IsActive = TRUE;
        """
        cursor.execute(sql_query, (shop_id,))
        shop = cursor.fetchone()
        cursor.close(); conn.close()
        
        if shop:
            if shop.get('Rating') is not None: shop['Rating'] = float(shop['Rating'])
            return True, "Lấy thông tin chi tiết cửa hàng thành công", shop
        return False, "Không tìm thấy cửa hàng hoặc cửa hàng đã ngừng hoạt động", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    
def create_shop(shop_name, address, hotline, manager_id, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_insert_shop = """
            INSERT INTO Shops (ShopName, Address, Hotline, ManagerID, Description) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING ShopID AS "ShopID", ShopName AS "ShopName", Description AS "Description", Rating AS "Rating";
        """
        cursor.execute(sql_insert_shop, (shop_name, address, hotline, manager_id, description))
        new_shop = cursor.fetchone()
        
        if new_shop.get('Rating') is not None: new_shop['Rating'] = float(new_shop['Rating'])
        
        cursor.execute("UPDATE Users SET RoleID = 2, UpdatedAt = CURRENT_TIMESTAMP WHERE UserID = %s AND RoleID = 3;", (manager_id,))
        conn.commit()
        cursor.close(); conn.close()
        return True, "Tạo cửa hàng và phân quyền thành công", new_shop
    except psycopg2.errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Mã người quản lý không tồn tại", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    
def update_shop(shop_id, user_id, role_id, shop_name=None, address=None, hotline=None, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (shop_id,))
        shop = cursor.fetchone()
        
        if not shop:
            cursor.close(); conn.close()
            return False, "Không tìm thấy cửa hàng", None
            
        if str(shop['managerid']) != str(user_id) and role_id != 1:
            cursor.close(); conn.close()
            return False, "Bạn không có quyền cập nhật cửa hàng này", None

        # ĐÃ BỔ SUNG CẬP NHẬT Description
        sql_query = """
            UPDATE Shops 
            SET ShopName = COALESCE(%s, ShopName), Address = COALESCE(%s, Address),
                Hotline = COALESCE(%s, Hotline), Description = COALESCE(%s, Description)
            WHERE ShopID = %s AND IsActive = TRUE
            RETURNING ShopID AS "ShopID", ShopName AS "ShopName", Address AS "Address", 
                      Hotline AS "Hotline", Description AS "Description", Rating AS "Rating", ManagerID AS "ManagerID";
        """
        cursor.execute(sql_query, (shop_name, address, hotline, description, shop_id))
        updated_shop = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_shop:
            if updated_shop.get('Rating') is not None: updated_shop['Rating'] = float(updated_shop['Rating'])
            return True, "Cập nhật thông tin cửa hàng thành công", updated_shop
        return False, "Cửa hàng đã ngừng hoạt động", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def toggle_shop_status(shop_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Shops SET IsActive = NOT IsActive, UpdatedAt = CURRENT_TIMESTAMP WHERE ShopID = %s
            RETURNING ShopID AS "ShopID", ShopName AS "ShopName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (shop_id,))
        updated_shop = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_shop:
            trang_thai = "Mở cửa hoạt động" if updated_shop["IsActive"] else "Đóng cửa tạm nghỉ"
            return True, f"Đã chuyển trạng thái cửa hàng sang: {trang_thai}", updated_shop
        return False, "Không tìm thấy cửa hàng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None