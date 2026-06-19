import psycopg2.extras
import math
from data_manager import get_db_connection

def get_all_orders(page=1, limit=10, user_id=None, role_id=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where_clause = ""
        params = []
        if role_id == 3: 
            where_clause = "WHERE UserID = %s"
            params.append(user_id)
        elif role_id == 2: 
            where_clause = "WHERE ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s)"
            params.append(user_id)

        cursor.execute(f"SELECT COUNT(*) FROM Orders {where_clause};", tuple(params))
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        sql_query = f"""
            SELECT 
                OrderID::text AS "OrderID", UserID::text AS "UserID", ShopID AS "ShopID",
                OrderDate AS "OrderDate", TotalAmount AS "TotalAmount", Status AS "Status",
                PaymentMethod AS "PaymentMethod", PaymentStatus AS "PaymentStatus", ShippingAddress AS "ShippingAddress"
            FROM Orders
            {where_clause}
            ORDER BY OrderDate DESC LIMIT %s OFFSET %s;
        """
        params.extend([limit, offset])
        cursor.execute(sql_query, tuple(params))
        orders = cursor.fetchall()
        cursor.close(); conn.close()
        
        for order in orders:
            if order.get('TotalAmount') is not None:
                order['TotalAmount'] = float(order['TotalAmount'])
        
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        pagination_result = {
            "orders": orders,
            "meta": { "total_items": total_items, "current_page": page, "total_pages": total_pages }
        }
        return True, "Lấy danh sách đơn hàng thành công", pagination_result
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_order_details(order_id, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_order = """
            SELECT OrderID::text AS "OrderID", UserID::text AS "UserID", ShopID AS "ShopID",
                   OrderDate AS "OrderDate", TotalAmount AS "TotalAmount", Status AS "Status",
                   PaymentMethod AS "PaymentMethod", PaymentStatus AS "PaymentStatus", ShippingAddress AS "ShippingAddress"
            FROM Orders WHERE OrderID = %s;
        """
        cursor.execute(sql_order, (order_id,))
        order_info = cursor.fetchone()
        
        if not order_info:
            cursor.close(); conn.close()
            return False, "Không tìm thấy đơn hàng", None

        if role_id == 3 and str(order_info['UserID']) != str(user_id):
            cursor.close(); conn.close()
            return False, "Bạn không có quyền xem đơn hàng này", None
        elif role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (order_info['ShopID'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền xem đơn hàng này", None

        order_dict = dict(order_info)
        if order_dict.get('TotalAmount') is not None:
            order_dict['TotalAmount'] = float(order_dict['TotalAmount'])

        sql_details = """
            SELECT od.OrderDetailID AS "OrderDetailID", od.ProductID AS "ProductID",
                   p.ProductName AS "ProductName", od.Quantity AS "Quantity", od.UnitPrice AS "UnitPrice"
            FROM OrderDetails od JOIN Products p ON od.ProductID = p.ProductID WHERE od.OrderID = %s;
        """
        cursor.execute(sql_details, (order_id,))
        order_items = cursor.fetchall()
        cursor.close(); conn.close()
        
        items_list = []
        for item in order_items:
            item_dict = dict(item)
            if item_dict.get('UnitPrice') is not None:
                item_dict['UnitPrice'] = float(item_dict['UnitPrice'])
            items_list.append(item_dict)
            
        order_dict['Items'] = items_list
        return True, "Lấy chi tiết đơn hàng thành công", order_dict
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def create_order(user_id, shop_id, shipping_address, payment_method, items_list):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        total_amount = 0
        valid_items = []
        
        for item in items_list:
            product_id = item['ProductID']
            buy_qty = item['Quantity']
            
            cursor.execute("""
                SELECT ProductName, Price, StockQuantity, ShopID, IsActive 
                FROM Products WHERE ProductID = %s FOR UPDATE;
            """, (product_id,))
            product = cursor.fetchone()
            
            if not product or product['shopid'] != shop_id or not product['isactive']:
                conn.rollback(); cursor.close(); conn.close()
                return False, f"Sản phẩm ID {product_id} không tồn tại hoặc không thuộc shop", None
                
            if product['stockquantity'] < buy_qty:
                conn.rollback(); cursor.close(); conn.close()
                return False, f"Sản phẩm '{product['productname']}' không đủ số lượng", None
                
            unit_price = float(product['price'])
            total_amount += unit_price * buy_qty
            valid_items.append({'ProductID': product_id, 'Quantity': buy_qty, 'UnitPrice': unit_price})

        # LOGIC MỚI THEO FE:
        # Nếu chuyển khoản -> Đã thanh toán luôn. Nếu COD -> Chưa thanh toán. Trạng thái chung là Chờ xác nhận.
        payment_status = 'Đã thanh toán' if payment_method == 'Chuyển khoản' else 'Chưa thanh toán'

        sql_insert_order = """
            INSERT INTO Orders (UserID, ShopID, TotalAmount, ShippingAddress, PaymentMethod, Status, PaymentStatus)
            VALUES (%s, %s, %s, %s, %s, 'Chờ xác nhận', %s)
            RETURNING OrderID::text AS "OrderID", OrderDate AS "OrderDate", Status AS "Status", PaymentMethod AS "PaymentMethod", PaymentStatus AS "PaymentStatus";
        """
        cursor.execute(sql_insert_order, (user_id, shop_id, total_amount, shipping_address, payment_method, payment_status))
        new_order = cursor.fetchone()
        order_id = new_order['OrderID']
        
        for v_item in valid_items:
            cursor.execute("""
                INSERT INTO OrderDetails (OrderID, ProductID, Quantity, UnitPrice)
                VALUES (%s, %s, %s, %s)
            """, (order_id, v_item['ProductID'], v_item['Quantity'], v_item['UnitPrice']))
            
            cursor.execute("""
                UPDATE Products 
                SET StockQuantity = StockQuantity - %s, SoldQuantity = SoldQuantity + %s 
                WHERE ProductID = %s
            """, (v_item['Quantity'], v_item['Quantity'], v_item['ProductID']))

        conn.commit()
        cursor.close(); conn.close()
        
        result_order = dict(new_order)
        result_order['TotalAmount'] = total_amount
        result_order['Items'] = valid_items
        return True, "Tạo đơn hàng thành công", result_order
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def update_order_status(order_id, new_status, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_id == 3:
            cursor.close(); conn.close()
            return False, "Khách hàng không có quyền cập nhật trạng thái đơn", None

        cursor.execute("SELECT ShopID FROM Orders WHERE OrderID = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            cursor.close(); conn.close()
            return False, "Đơn hàng không tồn tại", None

        if role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền cập nhật đơn hàng này", None

        sql_query = """
            UPDATE Orders SET Status = %s WHERE OrderID = %s AND Status != 'Đã hủy'
            RETURNING OrderID::text AS "OrderID", Status AS "Status", PaymentStatus AS "PaymentStatus";
        """
        cursor.execute(sql_query, (new_status, order_id))
        updated_order = cursor.fetchone()
        conn.commit()
        cursor.close(); conn.close()
        
        if updated_order: return True, "Cập nhật trạng thái thành công", dict(updated_order)
        return False, "Không tìm thấy đơn hàng hoặc đơn đã bị hủy", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def cancel_order(order_id, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT UserID, ShopID, Status, PaymentStatus FROM Orders WHERE OrderID = %s FOR UPDATE;", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            conn.rollback(); cursor.close(); conn.close()
            return False, "Không tìm thấy đơn hàng", None

        if role_id == 3 and str(order['userid']) != str(user_id):
            conn.rollback(); cursor.close(); conn.close()
            return False, "Bạn không có quyền hủy đơn hàng này", None
        elif role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                conn.rollback(); cursor.close(); conn.close()
                return False, "Bạn không có quyền hủy đơn hàng này", None
            
        if order['status'] in ['Đã hủy', 'Đang giao', 'Đã giao']:
            conn.rollback(); cursor.close(); conn.close()
            return False, f"Không thể hủy đơn hàng đang ở trạng thái: {order['status']}", None

        new_payment_status = 'Đã hoàn tiền' if order['paymentstatus'] == 'Đã thanh toán' else order['paymentstatus']

        cursor.execute("""
            UPDATE Orders SET Status = 'Đã hủy', PaymentStatus = %s WHERE OrderID = %s 
            RETURNING OrderID::text AS "OrderID", Status AS "Status", PaymentStatus AS "PaymentStatus";
        """, (new_payment_status, order_id))
        canceled_order = cursor.fetchone()

        cursor.execute("SELECT ProductID, Quantity FROM OrderDetails WHERE OrderID = %s;", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("""
                UPDATE Products 
                SET StockQuantity = StockQuantity + %s, SoldQuantity = GREATEST(SoldQuantity - %s, 0) 
                WHERE ProductID = %s;
            """, (item['quantity'], item['quantity'], item['productid']))

        conn.commit()
        cursor.close(); conn.close()
        return True, "Đã hủy đơn hàng và hoàn tất xử lý kho", dict(canceled_order)
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def get_order_payment_status(order_id, user_id, role_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT OrderID::text AS "OrderID", UserID, ShopID, PaymentStatus AS "PaymentStatus", TotalAmount AS "TotalAmount"
            FROM Orders WHERE OrderID = %s;
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order:
            cursor.close(); conn.close()
            return False, "Không tìm thấy đơn hàng", None

        if role_id == 3 and str(order['userid']) != str(user_id):
            cursor.close(); conn.close()
            return False, "Bạn không có quyền xem đơn hàng này", None
        elif role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                cursor.close(); conn.close()
                return False, "Bạn không có quyền xem đơn hàng này", None

        cursor.close(); conn.close()
        
        order_dict = dict(order)
        del order_dict['userid'] 
        del order_dict['shopid']
        order_dict['TotalAmount'] = float(order_dict['TotalAmount']) if order_dict.get('TotalAmount') else 0.0
        return True, "Lấy trạng thái thanh toán thành công", order_dict
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None

def confirm_mock_payment(order_id, user_id, role_id):
    """Cập nhật trạng thái thanh toán cho đơn COD. Chỉ dành cho Cửa hàng (Shop) khi nhận được tiền từ Shipper"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT UserID, ShopID, PaymentStatus FROM Orders WHERE OrderID = %s FOR UPDATE;", (order_id,))
        order = cursor.fetchone()
        
        if not order:
            conn.rollback(); cursor.close(); conn.close()
            return False, "Không tìm thấy đơn hàng để cập nhật", None

        # LOGIC MỚI: Khách hàng (Role 3) KHÔNG được tự bấm xác nhận. Shop (Role 2) mới là người xác nhận đã thu tiền.
        if role_id == 3:
            conn.rollback(); cursor.close(); conn.close()
            return False, "Khách hàng không thể tự xác nhận đã thanh toán tiền mặt", None
        elif role_id == 2:
            cursor.execute("SELECT ManagerID FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                conn.rollback(); cursor.close(); conn.close()
                return False, "Bạn không có quyền xác nhận thu tiền cho đơn của cửa hàng khác", None
            
        if order['paymentstatus'] == 'Đã thanh toán':
            conn.rollback(); cursor.close(); conn.close()
            return False, "Đơn hàng này đã được thanh toán từ trước", None

        cursor.execute("""
            UPDATE Orders 
            SET PaymentStatus = 'Đã thanh toán' 
            WHERE OrderID = %s
            RETURNING OrderID::text AS "OrderID", PaymentStatus AS "PaymentStatus", Status AS "Status", TotalAmount AS "TotalAmount";
        """, (order_id,))
        updated_order = cursor.fetchone()
        
        conn.commit()
        cursor.close(); conn.close()
        
        result_dict = dict(updated_order)
        result_dict['TotalAmount'] = float(result_dict['TotalAmount'])
        return True, "Xác nhận thu tiền đơn hàng thành công!", result_dict
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None