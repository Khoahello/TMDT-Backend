import psycopg2.extras
from data_manager import get_db_connection

def get_all_categories():
    """Hàm lấy toàn bộ danh sách danh mục"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            SELECT CategoryID AS "CategoryID", CategoryName AS "CategoryName", Description AS "Description"
            FROM Categories ORDER BY "CategoryID" ASC;
        """
        cursor.execute(sql_query)
        categories = cursor.fetchall()
        cursor.close(); conn.close()
        return True, "Lấy danh sách danh mục thành công", categories
    except Exception as e:
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def create_category(category_name, description=""):
    """Hàm thêm mới một danh mục vào hệ thống"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            INSERT INTO Categories (CategoryName, Description) 
            VALUES (%s, %s) 
            RETURNING CategoryID AS "CategoryID", CategoryName AS "CategoryName", Description AS "Description";
        """
        cursor.execute(sql_query, (category_name, description))
        new_category = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        return True, "Tạo danh mục mới thành công", new_category
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def update_category(category_id, category_name=None, description=None):
    """Hàm cập nhật thông tin danh mục linh hoạt"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Categories 
            SET CategoryName = COALESCE(%s, CategoryName), Description = COALESCE(%s, Description)
            WHERE CategoryID = %s
            RETURNING CategoryID AS "CategoryID", CategoryName AS "CategoryName", Description AS "Description";
        """
        cursor.execute(sql_query, (category_name, description, category_id))
        updated_category = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_category: return True, "Cập nhật thông tin danh mục thành công", updated_category
        return False, "Không tìm thấy danh mục để cập nhật", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def toggle_category_status(category_id):
    """Hàm đảo ngược trạng thái hiển thị (Bật/Tắt) của danh mục"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            UPDATE Categories SET IsActive = NOT IsActive WHERE CategoryID = %s
            RETURNING CategoryID AS "CategoryID", CategoryName AS "CategoryName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (category_id,))
        updated_category = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_category:
            trang_thai = "Hiển thị công khai" if updated_category["IsActive"] else "Ẩn khỏi giao diện"
            return True, f"Đã chuyển trạng thái danh mục sang: {trang_thai}", updated_category
        return False, "Không tìm thấy danh mục để cập nhật trạng thái", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None