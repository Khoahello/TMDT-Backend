import psycopg2.extras
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

def get_all_categories(role_name=None):
    """Lấy danh mục thông minh: Admin soi thấy Full bảng, Khách soi chỉ thấy danh mục IsActive=True"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where_clause = "" if role_name == 'Admin' else "WHERE IsActive = TRUE"
        
        sql_query = f"""
            SELECT CategoryID::text AS "CategoryID", CategoryName AS "CategoryName", 
                   Description AS "Description", IsActive AS "IsActive"
            FROM Categories {where_clause}
            ORDER BY CategoryName ASC;
        """
        cursor.execute(sql_query)
        categories = cursor.fetchall()
        return True, "Lấy danh sách danh mục thành công", categories
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()

def create_category(category_name, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            INSERT INTO Categories (CategoryName, Description) 
            VALUES (%s, %s) 
            RETURNING CategoryID::text AS "CategoryID", CategoryName AS "CategoryName", Description AS "Description", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (category_name, description))
        new_category = cursor.fetchone()
        conn.commit()
        return True, "Tạo danh mục mới thành công", dict(new_category)
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()
    
def update_category(category_id, category_name=None, description=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Categories 
            SET CategoryName = COALESCE(%s, CategoryName), Description = COALESCE(%s, Description)
            WHERE CategoryID = %s::uuid
            RETURNING CategoryID::text AS "CategoryID", CategoryName AS "CategoryName", Description AS "Description", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (category_name, description, category_id))
        updated_category = cursor.fetchone()
        conn.commit()
        
        if updated_category: return True, "Cập nhật thông tin danh mục thành công", dict(updated_category)
        return False, "Không tìm thấy danh mục để cập nhật", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID danh mục định danh không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()

def toggle_category_status(category_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Categories SET IsActive = NOT IsActive WHERE CategoryID = %s::uuid
            RETURNING CategoryID::text AS "CategoryID", CategoryName AS "CategoryName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (category_id,))
        updated_category = cursor.fetchone()
        conn.commit()
        
        if updated_category:
            trang_thai = "Hiển thị công khai" if updated_category["IsActive"] else "Ẩn khỏi giao diện"
            return True, f"Đã chuyển trạng thái danh mục sang: {trang_thai}", dict(updated_category)
        return False, "Không tìm thấy danh mục để cập nhật trạng thái", None
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID danh mục không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()