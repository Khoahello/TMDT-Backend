import psycopg2.extras
import math
from data_manager import get_db_connection
from psycopg2.errors import InvalidTextRepresentation

def get_all_orders(page=1, limit=10, user_id=None, role_name=None):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where_clause = ""
        params = []
        
        # [PHÂN QUYỀN ĐỘNG]: Xác định luồng truy vấn
        if role_name == 'Customer': 
            where_clause = "WHERE o.UserID = %s"
            params.append(user_id)
        elif role_name == 'Manager': 
            where_clause = "WHERE o.ShopID IN (SELECT ShopID FROM Shops WHERE ManagerID = %s)"
            params.append(user_id)

        # Tính tổng số đơn hàng (Dùng bí danh 'o' cho đồng bộ câu SQL dưới)
        cursor.execute(f"SELECT COUNT(*) FROM Orders o {where_clause};", tuple(params))
        total_items = cursor.fetchone()['count']
        offset = (page - 1) * limit
        
        # [TUYỆT KỸ JSON_AGG]: Gom toàn bộ Order, Tên Shop, và Danh sách Món hàng vào 1 phát Query!
        sql_query = f"""
            SELECT 
                o.OrderID::text AS "OrderID", 
                o.UserID::text AS "UserID", 
                o.ShopID::text AS "ShopID",
                s.ShopName AS "ShopName",
                o.OrderDate AS "OrderDate", 
                o.TotalAmount AS "TotalAmount", 
                o.Status AS "Status",
                o.PaymentMethod AS "PaymentMethod", 
                o.PaymentStatus AS "PaymentStatus", 
                o.ShippingAddress AS "ShippingAddress",
                o.ShippingName AS "ShippingName",
                o.ShippingPhone AS "ShippingPhone",
                
                -- Gom mảng các mặt hàng (Items) trực tiếp từ PostgreSQL
                COALESCE(
                    json_agg(
                        json_build_object(
                            'ProductID', od.ProductID::text,
                            'ProductName', p.ProductName,
                            'Quantity', od.Quantity,
                            'UnitPrice', od.UnitPrice,
                            'ImageURL', (
                                SELECT pi.ImageURL 
                                FROM ProductImages pi 
                                WHERE pi.ProductID = p.ProductID AND pi.IsPrimary = TRUE 
                                LIMIT 1
                            )
                        )
                    ) FILTER (WHERE od.OrderDetailID IS NOT NULL), '[]'::json
                ) AS "Items"

            FROM Orders o
            LEFT JOIN Shops s ON o.ShopID = s.ShopID
            LEFT JOIN OrderDetails od ON o.OrderID = od.OrderID
            LEFT JOIN Products p ON od.ProductID = p.ProductID
            {where_clause}
            GROUP BY o.OrderID, s.ShopName
            ORDER BY o.OrderDate DESC 
            LIMIT %s OFFSET %s;
        """
        
        params.extend([limit, offset])
        cursor.execute(sql_query, tuple(params))
        orders = cursor.fetchall()
        
        # Định dạng lại dữ liệu thập phân cho gọn
        for order in orders:
            if order.get('TotalAmount') is not None:
                order['TotalAmount'] = float(order['TotalAmount'])
            
            # Xử lý mảng Items (Chuyển chuỗi JSON của Postgres thành mảng Python)
            if order.get('Items'):
                for item in order['Items']:
                    if item.get('UnitPrice') is not None:
                        item['UnitPrice'] = float(item['UnitPrice'])
        
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
        pagination_result = {
            "orders": orders,
            "meta": { "total_items": total_items, "current_page": page, "total_pages": total_pages }
        }
        return True, "Lấy danh sách đơn hàng thành công", pagination_result
        
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def get_order_details(order_id, user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_order = """
            SELECT OrderID::text AS "OrderID", UserID::text AS "UserID", ShopID::text AS "ShopID",
                   OrderDate AS "OrderDate", TotalAmount AS "TotalAmount", Status AS "Status",
                   PaymentMethod AS "PaymentMethod", PaymentStatus AS "PaymentStatus", ShippingAddress AS "ShippingAddress"
            FROM Orders WHERE OrderID = %s;
        """
        cursor.execute(sql_order, (order_id,))
        order_info = cursor.fetchone()
        
        if not order_info:
            return False, "Không tìm thấy đơn hàng", None

        # [SO QUYỀN ĐỘNG]
        if role_name == 'Customer' and str(order_info['UserID']) != str(user_id):
            return False, "Bạn không có quyền xem đơn hàng này", None
        elif role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (order_info['ShopID'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                return False, "Bạn không có quyền xem đơn hàng này", None

        order_dict = dict(order_info)
        if order_dict.get('TotalAmount') is not None:
            order_dict['TotalAmount'] = float(order_dict['TotalAmount'])

        # Ép ProductID::text
        sql_details = """
            SELECT od.OrderDetailID::text AS "OrderDetailID", od.ProductID::text AS "ProductID",
                   p.ProductName AS "ProductName", od.Quantity AS "Quantity", od.UnitPrice AS "UnitPrice"
            FROM OrderDetails od JOIN Products p ON od.ProductID = p.ProductID WHERE od.OrderID = %s;
        """
        cursor.execute(sql_details, (order_id,))
        order_items = cursor.fetchall()
        
        items_list = []
        for item in order_items:
            item_dict = dict(item)
            if item_dict.get('UnitPrice') is not None:
                item_dict['UnitPrice'] = float(item_dict['UnitPrice'])
            items_list.append(item_dict)
            
        order_dict['Items'] = items_list
        return True, "Lấy chi tiết đơn hàng thành công", order_dict
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID đơn hàng không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def create_order(user_id, shop_id, shipping_address, shipping_name, shipping_phone, note, payment_method, items_list):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Nếu thiếu Tên/SĐT, bốc từ profile của User bù vào
        if not shipping_name or not shipping_phone or not shipping_address:
            cursor.execute("SELECT FullName, PhoneNumber, Address FROM Users WHERE UserID = %s;", (user_id,))
            u = cursor.fetchone()
            if u:
                shipping_name = shipping_name or u['fullname']
                shipping_phone = shipping_phone or u['phonenumber']
                shipping_address = shipping_address or u['address']

        total_amount = 0
        valid_items = []
        items_list = sorted(items_list, key=lambda x: str(x['ProductID']))
        
        for item in items_list:
            product_id_str = str(item['ProductID']).strip()
            buy_qty = int(item['Quantity'])
            
            cursor.execute("SELECT ProductName, Price, StockQuantity, ShopID::text AS shopid, IsActive FROM Products WHERE ProductID = %s FOR UPDATE;", (product_id_str,))
            product = cursor.fetchone()
            
            if not product or str(product['shopid']) != str(shop_id) or not product['isactive']:
                conn.rollback()
                return False, f"Sản phẩm (ID: {product_id_str}) không tồn tại hoặc đã khóa", None
                
            if int(product['stockquantity']) < buy_qty:
                conn.rollback()
                return False, f"Sản phẩm '{product['productname']}' không đủ hàng trong kho", None
                
            unit_price = float(product['price'])
            total_amount += unit_price * buy_qty
            valid_items.append({'ProductID': product_id_str, 'Quantity': buy_qty, 'UnitPrice': unit_price})

        payment_status = 'Đã thanh toán' if payment_method == 'Chuyển khoản' else 'Chưa thanh toán'

        sql_insert_order = """
            INSERT INTO Orders (UserID, ShopID, TotalAmount, ShippingAddress, ShippingName, ShippingPhone, Note, PaymentMethod, Status, PaymentStatus)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Chờ xác nhận', %s)
            RETURNING OrderID::text AS "OrderID", OrderDate AS "OrderDate", Status AS "Status", PaymentMethod AS "PaymentMethod", PaymentStatus AS "PaymentStatus";
        """
        cursor.execute(sql_insert_order, (str(user_id), str(shop_id), total_amount, shipping_address, shipping_name, shipping_phone, note, payment_method, payment_status))
        new_order = cursor.fetchone()
        order_id_created = new_order['OrderID']
        
        for v_item in valid_items:
            cursor.execute("INSERT INTO OrderDetails (OrderID, ProductID, Quantity, UnitPrice) VALUES (%s, %s, %s, %s)", (order_id_created, v_item['ProductID'], v_item['Quantity'], v_item['UnitPrice']))
            cursor.execute("UPDATE Products SET StockQuantity = StockQuantity - %s, SoldQuantity = SoldQuantity + %s WHERE ProductID = %s", (v_item['Quantity'], v_item['Quantity'], v_item['ProductID']))

        conn.commit()
        result_order = dict(new_order)
        result_order['TotalAmount'] = total_amount
        result_order['Items'] = valid_items
        return True, "Tạo đơn hàng thành công", result_order
        
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi xử lý đơn hàng: {str(e)}", None
    finally:
        if conn: conn.close()

def update_order_status(order_id, new_status, user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if role_name == 'Customer':
            return False, "Khách hàng không có quyền cập nhật trạng thái đơn", None

        cursor.execute("SELECT ShopID::text FROM Orders WHERE OrderID = %s", (order_id,))
        order = cursor.fetchone()
        if not order: return False, "Đơn hàng không tồn tại", None

        if role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                return False, "Bạn không có quyền cập nhật đơn hàng của tiệm khác", None

        sql_query = """
            UPDATE Orders SET Status = %s WHERE OrderID = %s AND Status != 'Đã hủy'
            RETURNING OrderID::text AS "OrderID", Status AS "Status", PaymentStatus AS "PaymentStatus";
        """
        cursor.execute(sql_query, (new_status, order_id))
        updated_order = cursor.fetchone()
        conn.commit()
        
        if updated_order: return True, "Cập nhật trạng thái thành công", dict(updated_order)
        return False, "Không tìm thấy đơn hàng hoặc đơn đã bị hủy trước đó", None
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID đơn hàng không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def cancel_order(order_id, user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT UserID::text AS "userid", ShopID::text AS "shopid", Status AS "status", PaymentStatus AS "paymentstatus" FROM Orders WHERE OrderID = %s FOR UPDATE;', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            conn.rollback()
            return False, "Không tìm thấy đơn hàng", None

        if role_name == 'Customer' and str(order['userid']) != str(user_id):
            conn.rollback()
            return False, "Bạn không có quyền hủy đơn hàng này", None
        elif role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                conn.rollback()
                return False, "Bạn không có quyền hủy đơn hàng của tiệm khác", None
            
        if order['status'] in ['Đã hủy', 'Đang giao', 'Đã giao']:
            conn.rollback()
            return False, f"Không thể hủy đơn hàng đang ở trạng thái: {order['status']}", None

        new_payment_status = 'Đã hoàn tiền' if order['paymentstatus'] == 'Đã thanh toán' else order['paymentstatus']

        cursor.execute("""
            UPDATE Orders SET Status = 'Đã hủy', PaymentStatus = %s WHERE OrderID = %s 
            RETURNING OrderID::text AS "OrderID", Status AS "Status", PaymentStatus AS "PaymentStatus";
        """, (new_payment_status, order_id))
        canceled_order = cursor.fetchone()

        cursor.execute("SELECT ProductID::text AS productid, Quantity FROM OrderDetails WHERE OrderID = %s;", (order_id,))
        for item in cursor.fetchall():
            cursor.execute("""
                UPDATE Products 
                SET StockQuantity = StockQuantity + %s, SoldQuantity = GREATEST(SoldQuantity - %s, 0) 
                WHERE ProductID = %s;
            """, (item['quantity'], item['quantity'], item['productid']))

        conn.commit()
        return True, "Đã hủy đơn hàng và hoàn tất xử lý trả kho", dict(canceled_order)
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã ID đơn hàng không hợp lệ", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def get_order_payment_status(order_id, user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT OrderID::text AS "OrderID", UserID::text AS userid, ShopID::text AS shopid, PaymentStatus AS "PaymentStatus", TotalAmount AS "TotalAmount"
            FROM Orders WHERE OrderID = %s;
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order: return False, "Không tìm thấy đơn hàng", None

        if role_name == 'Customer' and str(order['userid']) != str(user_id):
            return False, "Bạn không có quyền xem đơn hàng này", None
        elif role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                return False, "Bạn không có quyền xem đơn hàng này", None

        order_dict = dict(order)
        del order_dict['userid'] 
        del order_dict['shopid']
        order_dict['TotalAmount'] = float(order_dict['TotalAmount']) if order_dict.get('TotalAmount') else 0.0
        return True, "Lấy trạng thái thanh toán thành công", order_dict
        
    except InvalidTextRepresentation:
        return False, "Mã ID đơn hàng không đúng định dạng", None
    except Exception as e:
        return False, str(e), None
    finally:
        if conn: conn.close()

def confirm_mock_payment(order_id, user_id, role_name):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối CSDL", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('SELECT UserID::text AS userid, ShopID::text AS shopid, PaymentStatus AS paymentstatus FROM Orders WHERE OrderID = %s FOR UPDATE;', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            conn.rollback()
            return False, "Không tìm thấy đơn hàng để cập nhật", None

        if role_name == 'Customer':
            conn.rollback()
            return False, "Khách hàng không thể tự xác nhận đã thanh toán tiền mặt", None
        elif role_name == 'Manager':
            cursor.execute("SELECT ManagerID::text FROM Shops WHERE ShopID = %s", (order['shopid'],))
            shop = cursor.fetchone()
            if not shop or str(shop['managerid']) != str(user_id):
                conn.rollback()
                return False, "Bạn không có quyền xác nhận thu tiền cho đơn của tiệm khác", None
            
        if order['paymentstatus'] == 'Đã thanh toán':
            conn.rollback()
            return False, "Đơn hàng này đã được thanh toán từ trước", None

        cursor.execute("""
            UPDATE Orders 
            SET PaymentStatus = 'Đã thanh toán', UpdatedAt = CURRENT_TIMESTAMP
            WHERE OrderID = %s
            RETURNING OrderID::text AS "OrderID", PaymentStatus AS "PaymentStatus", Status AS "Status", TotalAmount AS "TotalAmount";
        """, (order_id,))
        updated_order = cursor.fetchone()
        conn.commit()
        
        result_dict = dict(updated_order)
        result_dict['TotalAmount'] = float(result_dict['TotalAmount'])
        return True, "Xác nhận thu tiền đơn hàng COD thành công!", result_dict
        
    except InvalidTextRepresentation:
        if conn: conn.rollback()
        return False, "Mã đơn hàng không đúng định dạng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()
