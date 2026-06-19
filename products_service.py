import psycopg2.extras
from psycopg2 import errors 
import math
from data_manager import get_db_connection

def get_all_products(page=1, limit=10):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) FROM Products WHERE IsActive = TRUE;")
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        sql_query = """
            SELECT 
                p.ProductID AS "ProductID", p.ProductName AS "ProductName", 
                p.Price AS "Price", p.StockQuantity AS "StockQuantity", 
                p.SoldQuantity AS "SoldQuantity",
                p.CategoryID AS "CategoryID", p.ShopID AS "ShopID", 
                p.IsActive AS "IsActive", p.CreatedAt AS "CreatedAt",
                img.ImageURL AS "PrimaryImage"
            FROM Products p
            LEFT JOIN ProductImages img ON p.ProductID = img.ProductID AND img.IsPrimary = TRUE
            WHERE p.IsActive = TRUE
            ORDER BY p.CreatedAt DESC, p.ProductID ASC
            LIMIT %s OFFSET %s;
        """
        cursor.execute(sql_query, (limit, offset))
        products = cursor.fetchall()
        cursor.close(); conn.close()
        
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        pagination_result = {
            "products": products,
            "meta": { "total_items": total_items, "current_page": page, "total_pages": total_pages }
        }
        return True, "Lấy danh sách sản phẩm thành công", pagination_result
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def get_product_details(product_id):
    """Lấy chi tiết SP kèm Mô tả, Lượt bán, Thông số kỹ thuật và Hình ảnh"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_product = """
            SELECT ProductID AS "ProductID", ProductName AS "ProductName", Price AS "Price", 
                   StockQuantity AS "StockQuantity", SoldQuantity AS "SoldQuantity", 
                   Description AS "Description", CategoryID AS "CategoryID", ShopID AS "ShopID", 
                   IsActive AS "IsActive", CreatedAt AS "CreatedAt"
            FROM Products WHERE ProductID = %s AND IsActive = TRUE;
        """
        cursor.execute(sql_product, (product_id,))
        product = cursor.fetchone()
        
        if not product:
            cursor.close(); conn.close()
            return False, "Sản phẩm không tồn tại", None
            
        # Lấy hình ảnh
        cursor.execute('SELECT ImageID AS "ImageID", ImageURL AS "ImageURL", IsPrimary AS "IsPrimary" FROM ProductImages WHERE ProductID = %s ORDER BY IsPrimary DESC, ImageID ASC;', (product_id,))
        product["Images"] = cursor.fetchall()

        # LẤY THÔNG SỐ KỸ THUẬT
        cursor.execute('SELECT SpecKey AS "Key", SpecValue AS "Value" FROM ProductSpecifications WHERE ProductID = %s;', (product_id,))
        product["Specifications"] = cursor.fetchall()
        
        cursor.close(); conn.close()
        return True, "Lấy chi tiết sản phẩm thành công", product
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    
def create_product(product_name, price, stock_quantity, category_id, shop_id, user_id, role_id, image_urls=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Kiểm tra quyền sở hữu cửa hàng
        if role_id != 1: 
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (shop_id,))
            shop = cursor.fetchone()
            if not shop:
                cursor.close(); conn.close()
                return False, "Cửa hàng không tồn tại", None
            if str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền thêm sản phẩm vào cửa hàng này", None

        sql_insert_product = """
            INSERT INTO Products (ProductName, Price, StockQuantity, CategoryID, ShopID) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING ProductID, ProductName, Price, StockQuantity, CategoryID, ShopID, IsActive, CreatedAt;
        """
        cursor.execute(sql_insert_product, (product_name, price, stock_quantity, category_id, shop_id))
        new_product = cursor.fetchone()
        product_id = new_product['productid']
        
        new_product['Images'] = [] 
        new_product['PrimaryImage'] = None 
        
        if image_urls and len(image_urls) > 0:
            for index, url in enumerate(image_urls):
                is_primary = (index == 0) 
                sql_insert_image = """
                    INSERT INTO ProductImages (ProductID, ImageURL, IsPrimary)
                    VALUES (%s, %s, %s) RETURNING ImageURL;
                """
                cursor.execute(sql_insert_image, (product_id, url, is_primary))
                new_product['Images'].append(url)
                if is_primary: new_product['PrimaryImage'] = url
                    
        conn.commit()
        cursor.close(); conn.close()
        return True, "Tạo sản phẩm mới thành công", new_product
    except errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Mã Danh mục hoặc Cửa hàng không tồn tại", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def update_product(product_id, user_id, role_id, product_name=None, price=None, stock_quantity=None, category_id=None, image_urls=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_id != 1:
            cursor.execute("""
                SELECT s.ManagerID FROM Products p
                JOIN Shops s ON p.ShopID = s.ShopID
                WHERE p.ProductID = %s
            """, (product_id,))
            shop = cursor.fetchone()
            if not shop:
                cursor.close(); conn.close()
                return False, "Sản phẩm không tồn tại", None
            if str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền chỉnh sửa sản phẩm này", None

        sql_update_info = """
            UPDATE Products 
            SET ProductName = COALESCE(%s, ProductName), Price = COALESCE(%s, Price),
                StockQuantity = COALESCE(%s, StockQuantity), CategoryID = COALESCE(%s, CategoryID),
                UpdatedAt = CURRENT_TIMESTAMP
            WHERE ProductID = %s AND IsActive = TRUE
            RETURNING ProductID, ProductName, Price, StockQuantity, CategoryID, ShopID, IsActive, UpdatedAt;
        """
        cursor.execute(sql_update_info, (product_name, price, stock_quantity, category_id, product_id))
        updated_product = cursor.fetchone()
        
        if not updated_product:
            cursor.close(); conn.close()
            return False, "Không tìm thấy sản phẩm hoặc sản phẩm đã bị khóa", None

        result_dict = dict(updated_product)
        if result_dict.get('price') is not None:
            result_dict['price'] = float(result_dict['price'])

        result_dict['Images'] = []
        if image_urls and len(image_urls) > 0:
            cursor.execute("DELETE FROM ProductImages WHERE ProductID = %s", (product_id,))
            for index, url in enumerate(image_urls):
                is_primary = (index == 0)
                cursor.execute("""
                    INSERT INTO ProductImages (ProductID, ImageURL, IsPrimary)
                    VALUES (%s, %s, %s)
                """, (product_id, url, is_primary))
                result_dict['Images'].append(url)
                if is_primary: result_dict['PrimaryImage'] = url
        else:
            cursor.execute("""
                SELECT ImageURL, IsPrimary FROM ProductImages 
                WHERE ProductID = %s ORDER BY IsPrimary DESC, ImageID ASC
            """, (product_id,))
            old_images = cursor.fetchall()
            for img in old_images: result_dict['Images'].append(img['imageurl'])
            result_dict['PrimaryImage'] = old_images[0]['imageurl'] if old_images else None

        conn.commit()
        cursor.close(); conn.close()
        return True, "Cập nhật sản phẩm thành công", result_dict
    except errors.ForeignKeyViolation:
        if conn: conn.rollback()
        return False, "Mã Danh mục không tồn tại", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def toggle_product_status(product_id, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_id != 1:
            cursor.execute("""
                SELECT s.ManagerID FROM Products p
                JOIN Shops s ON p.ShopID = s.ShopID
                WHERE p.ProductID = %s
            """, (product_id,))
            shop = cursor.fetchone()
            if not shop:
                cursor.close(); conn.close()
                return False, "Sản phẩm không tồn tại", None
            if str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền khóa/mở sản phẩm này", None

        sql_query = """
            UPDATE Products SET IsActive = NOT IsActive, UpdatedAt = CURRENT_TIMESTAMP
            WHERE ProductID = %s
            RETURNING ProductID AS "ProductID", ProductName AS "ProductName", IsActive AS "IsActive";
        """
        cursor.execute(sql_query, (product_id,))
        updated_prod = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_prod:
            trang_thai = "Đang mở bán" if updated_prod["IsActive"] else "Tạm ẩn / Ngừng kinh doanh"
            return True, f"Đã chuyển trạng thái sản phẩm sang: {trang_thai}", dict(updated_prod)
        return False, "Không tìm thấy sản phẩm", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    
def submit_product_review(product_id, user_id, rating, review_text=""):
    """Lưu đánh giá kèm nội dung chữ"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            INSERT INTO ProductReviews (ProductID, UserID, Rating, ReviewText)
            VALUES (%s, %s, %s, %s)
            RETURNING ReviewID AS "ReviewID", Rating AS "Rating", ReviewText AS "ReviewText";
        """
        cursor.execute(sql_query, (product_id, user_id, rating, review_text))
        new_review = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        return True, "Cảm ơn bạn đã đánh giá sản phẩm!", dict(new_review)
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_product_rating_stats(product_id):
    """Lấy Thống kê sao VÀ Danh sách chi tiết các bài đánh giá (Kèm Tên, Avatar)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Lấy thống kê tổng quan
        cursor.execute("""
            SELECT COUNT(ReviewID) AS "TotalReviews", COALESCE(ROUND(AVG(Rating), 1), 0) AS "AverageRating"
            FROM ProductReviews WHERE ProductID = %s;
        """, (product_id,))
        stats = cursor.fetchone()
        
        # Lấy danh sách đánh giá chi tiết
        cursor.execute("""
            SELECT 
                pr.ReviewID AS "ReviewID",
                pr.Rating AS "Rating",
                pr.ReviewText AS "ReviewText",
                pr.CreatedAt AS "CreatedAt",
                u.FullName AS "ReviewerName",
                u.AvatarURL AS "ReviewerAvatar"
            FROM ProductReviews pr
            JOIN Users u ON pr.UserID = u.UserID
            WHERE pr.ProductID = %s
            ORDER BY pr.CreatedAt DESC;
        """, (product_id,))
        reviews_list = cursor.fetchall()
        
        cursor.close(); conn.close()
        
        result = {
            "TotalReviews": int(stats["TotalReviews"]),
            "AverageRating": float(stats["AverageRating"]),
            "Reviews": [dict(r) for r in reviews_list]
        }
        
        return True, "Lấy thống kê và danh sách đánh giá thành công", result
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None