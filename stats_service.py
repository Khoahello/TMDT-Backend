import psycopg2.extras
from data_manager import get_db_connection

def get_total_revenue(start_date, end_date, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_sql = """
            SELECT 
                COUNT(o.OrderID) AS "TotalOrders",
                SUM(CASE WHEN o.Status != 'Đã hủy' THEN 1 ELSE 0 END) AS "SuccessfulOrders",
                SUM(CASE WHEN o.Status = 'Đã hủy' THEN 1 ELSE 0 END) AS "CancelledOrders",
                COALESCE(SUM(CASE WHEN o.Status != 'Đã hủy' THEN o.TotalAmount ELSE 0 END), 0) AS "TotalRevenue"
            FROM Orders o
            WHERE o.OrderDate::date >= %s AND o.OrderDate::date <= %s
        """
        params = [start_date, end_date]
        
        # Nếu là Manager, chỉ tính đơn hàng thuộc các shop của họ
        if role_id == 2:
            base_sql += " AND o.ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s) "
            params.append(user_id)
            
        cursor.execute(base_sql, tuple(params))
        result = dict(cursor.fetchone())
        result['TotalRevenue'] = float(result['TotalRevenue'])
        
        cursor.close(); conn.close()
        return True, "Thống kê tổng doanh thu thành công", result
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_top_products(limit=10, start_date=None, end_date=None, user_id=None, role_id=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_sql = """
            SELECT 
                p.ProductID AS "ProductID", p.ProductName AS "ProductName", c.CategoryName AS "CategoryName",
                SUM(od.Quantity) AS "TotalSoldQuantity", SUM(od.Quantity * od.UnitPrice) AS "RevenueGenerated"
            FROM OrderDetails od
            JOIN Orders o ON od.OrderID = o.OrderID
            JOIN Products p ON od.ProductID = p.ProductID
            LEFT JOIN Categories c ON p.CategoryID = c.CategoryID
            WHERE o.Status != 'Đã hủy'
        """
        params = []
        if start_date and end_date:
            base_sql += " AND o.OrderDate::date >= %s AND o.OrderDate::date <= %s "
            params.extend([start_date, end_date])
            
        if role_id == 2:
            base_sql += " AND o.ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s) "
            params.append(user_id)
            
        base_sql += " GROUP BY p.ProductID, p.ProductName, c.CategoryName ORDER BY \"RevenueGenerated\" DESC LIMIT %s;"
        params.append(limit)
        
        cursor.execute(base_sql, tuple(params))
        products = cursor.fetchall()
        cursor.close(); conn.close()
        
        result_list = []
        for p in products:
            item = dict(p)
            item['TotalSoldQuantity'] = int(item['TotalSoldQuantity'])
            item['RevenueGenerated'] = float(item['RevenueGenerated'])
            result_list.append(item)
            
        return True, "Lấy danh sách sản phẩm bán chạy thành công", result_list
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_order_status_breakdown(user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_sql = 'SELECT Status AS "Status", COUNT(OrderID) AS "Count" FROM Orders WHERE 1=1 '
        params = []
        if role_id == 2:
            base_sql += " AND ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s) "
            params.append(user_id)
        base_sql += ' GROUP BY Status;'
        
        cursor.execute(base_sql, tuple(params))
        stats = cursor.fetchall()
        cursor.close(); conn.close()
        return True, "Thống kê trạng thái đơn hàng thành công", [dict(s) for s in stats]
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_revenue_by_shop(start_date, end_date, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_sql = """
            SELECT 
                s.ShopID AS "ShopID", s.ShopName AS "ShopName", COALESCE(SUM(o.TotalAmount), 0) AS "Revenue"
            FROM Shops s
            LEFT JOIN Orders o ON s.ShopID = o.ShopID AND o.Status != 'Đã hủy' AND o.OrderDate::date >= %s AND o.OrderDate::date <= %s
            WHERE 1=1
        """
        params = [start_date, end_date]
        if role_id == 2:
            base_sql += " AND s.ManagerID = %s "
            params.append(user_id)
            
        base_sql += ' GROUP BY s.ShopID, s.ShopName ORDER BY "Revenue" DESC;'
        
        cursor.execute(base_sql, tuple(params))
        shops = cursor.fetchall()
        cursor.close(); conn.close()
        
        result_list = [dict(s) for s in shops]
        for s in result_list: s['Revenue'] = float(s['Revenue'])
        return True, "Thống kê doanh thu theo cửa hàng thành công", result_list
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_revenue_by_category(start_date, end_date, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base_sql = """
            SELECT 
                c.CategoryID AS "CategoryID", c.CategoryName AS "CategoryName", COALESCE(SUM(od.Quantity * od.UnitPrice), 0) AS "Revenue"
            FROM Categories c
            JOIN Products p ON c.CategoryID = p.CategoryID 
            JOIN OrderDetails od ON p.ProductID = od.ProductID 
            JOIN Orders o ON od.OrderID = o.OrderID
            WHERE o.Status != 'Đã hủy' AND o.OrderDate::date >= %s AND o.OrderDate::date <= %s
        """
        params = [start_date, end_date]
        if role_id == 2:
            base_sql += " AND o.ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s) "
            params.append(user_id)
            
        base_sql += ' GROUP BY c.CategoryID, c.CategoryName ORDER BY "Revenue" DESC;'
        
        cursor.execute(base_sql, tuple(params))
        categories = cursor.fetchall()
        cursor.close(); conn.close()
        
        result_list = [dict(c) for c in categories]
        for c in result_list: c['Revenue'] = float(c['Revenue'])
        return True, "Thống kê doanh thu theo danh mục thành công", result_list
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None