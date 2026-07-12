import psycopg2.extras
from data_manager import get_db_connection

def _get_or_create_cart(cursor, user_id):
    """Hàm nội bộ: Tìm giỏ hàng của User, nếu chưa có thì tạo mới."""
    cursor.execute("SELECT CartID FROM Cart WHERE UserID = %s;", (user_id,))
    cart = cursor.fetchone()
    if cart: return cart['cartid'] if isinstance(cart, dict) else cart[0]
        
    cursor.execute("INSERT INTO Cart (UserID) VALUES (%s) RETURNING CartID;", (user_id,))
    new_cart = cursor.fetchone()
    return new_cart['cartid'] if isinstance(new_cart, dict) else new_cart[0]

# ================= 1. API GIỎ HÀNG CHÍNH (/api/cart) =================

def get_cart(user_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cart_id = _get_or_create_cart(cursor, user_id)
        
        sql = """
            SELECT ci.CartItemID::text AS item_id, 
                   ci.ProductID::text AS product_id, 
                   p.ProductName AS product_name, 
                   p.Price AS price, 
                   ci.Quantity AS quantity,
                   (p.Price * ci.Quantity) AS sub_total,
                   COALESCE(pi.ImageURL, '') AS image_url,
                   p.ShopID::text AS shop_id
            FROM CartItems ci
            JOIN Products p ON ci.ProductID = p.ProductID
            LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID AND pi.IsPrimary = TRUE
            WHERE ci.CartID = %s
            ORDER BY ci.CreatedAt DESC;
        """
        cursor.execute(sql, (cart_id,))
        items = cursor.fetchall()
        total_amount = sum(item['sub_total'] for item in items)
        
        return True, "Lấy giỏ hàng thành công", {
            "cart_id": str(cart_id),
            "total_amount": total_amount,
            "items": items
        }
    except Exception as e: return False, str(e), None
    finally:
        if conn: conn.close()

def clear_cart(user_id):
    """Xóa trắng giỏ hàng"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor()
        cart_id = _get_or_create_cart(cursor, user_id)
        cursor.execute("DELETE FROM CartItems WHERE CartID = %s;", (cart_id,))
        cursor.execute("UPDATE Cart SET UpdatedAt = CURRENT_TIMESTAMP WHERE CartID = %s;", (cart_id,))
        conn.commit()
        return True, "Đã làm trống giỏ hàng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def checkout_cart(user_id, payment_method='COD', shipping_name=None, shipping_phone=None, shipping_address=None, note=None, voucher_code=None):
    """Nghiệp vụ Checkout: Lấy TRỰC TIẾP dữ liệu FE truyền xuống để lưu (Không lấy từ bảng Users)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu hệ thống", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. XỬ LÝ VOUCHER (NẾU CÓ)
        discount_amount = 0
        if voucher_code:
            cursor.execute("SELECT VoucherCode, DiscountAmount, IsActive, ExpiryDate FROM Vouchers WHERE VoucherCode = %s;", (voucher_code.strip(),))
            voucher = cursor.fetchone()
            if not voucher or not voucher['isactive']:
                return False, "Mã giảm giá (Voucher) không hợp lệ hoặc đã hết hạn!", None
            discount_amount = voucher['discountamount']

        # 2. TRÍCH XUẤT SẢN PHẨM TRONG GIỎ
        cursor.execute("SELECT CartID FROM Cart WHERE UserID = %s;", (user_id,))
        cart_row = cursor.fetchone()
        if not cart_row: return False, "Giỏ hàng của bạn đang trống", None
        cart_id = cart_row['cartid']

        cursor.execute("""
            SELECT ci.ProductID, ci.Quantity, p.Price, p.ShopID, p.StockQuantity
            FROM CartItems ci JOIN Products p ON ci.ProductID = p.ProductID
            WHERE ci.CartID = %s;
        """, (cart_id,))
        items = cursor.fetchall()
        
        if not items: return False, "Giỏ hàng trống, không thể thanh toán!", None
            
        for item in items:
            if item['quantity'] > item['stockquantity']:
                return False, "Một số sản phẩm trong giỏ không đủ tồn kho cung ứng!", None

        # 3. GOM NHÓM SẢN PHẨM THEO CỬA HÀNG (SPLIT ORDER)
        shop_orders = {}
        for item in items:
            shop_id = item['shopid']
            if shop_id not in shop_orders:
                shop_orders[shop_id] = {'sub_total': 0, 'items': []}
            shop_orders[shop_id]['items'].append(item)
            shop_orders[shop_id]['sub_total'] += (item['price'] * item['quantity'])

        created_orders = []
        voucher_applied = False

        # 4. GHI ĐƠN HÀNG VÀO POSTGRESQL
        for shop_id, order_data in shop_orders.items():
            sub_total = order_data['sub_total']
            current_discount = 0
            if voucher_code and not voucher_applied:
                current_discount = discount_amount
                voucher_applied = True
            total_amount = max(0, sub_total - current_discount)

            cursor.execute("""
                INSERT INTO Orders (
                    UserID, ShopID, TotalAmount, PaymentMethod, 
                    ShippingAddress, ShippingName, ShippingPhone, Note,
                    VoucherCode, DiscountAmount
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING OrderID::text;
            """, (
                user_id, shop_id, total_amount, payment_method,
                shipping_address, shipping_name, shipping_phone, note,
                voucher_code if current_discount > 0 else None, current_discount
            ))
            new_order_id = cursor.fetchone()['orderid']
            
            for item in order_data['items']:
                cursor.execute("""
                    INSERT INTO OrderDetails (OrderID, ProductID, Quantity, UnitPrice)
                    VALUES (%s, %s, %s, %s);
                """, (new_order_id, item['productid'], item['quantity'], item['price']))
                
                cursor.execute("""
                    UPDATE Products SET StockQuantity = StockQuantity - %s, SoldQuantity = SoldQuantity + %s WHERE ProductID = %s;
                """, (item['quantity'], item['quantity'], item['productid']))
                
            created_orders.append(new_order_id)

        cursor.execute("DELETE FROM CartItems WHERE CartID = %s;", (cart_id,))
        cursor.execute("UPDATE Cart SET UpdatedAt = CURRENT_TIMESTAMP WHERE CartID = %s;", (cart_id,))
        
        conn.commit()
        return True, "Đặt hàng thành công!", {"created_orders": created_orders}
        
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi giao dịch thanh toán: {str(e)}", None
    finally:
        if conn: conn.close()

# ================= 2. API CÁC ITEM TRONG GIỎ (/api/cart/items) =================

def add_item(user_id, product_id, quantity):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cart_id = _get_or_create_cart(cursor, user_id)
        
        cursor.execute("SELECT StockQuantity FROM Products WHERE ProductID = %s AND IsActive = TRUE;", (product_id,))
        product = cursor.fetchone()
        if not product: return False, "Sản phẩm không tồn tại", None
            
        cursor.execute("SELECT CartItemID, Quantity FROM CartItems WHERE CartID = %s AND ProductID = %s;", (cart_id, product_id))
        existing = cursor.fetchone()
        
        if existing:
            new_qty = existing['quantity'] + quantity
            if new_qty > product['stockquantity']: return False, "Không đủ hàng tồn kho", None
            cursor.execute("UPDATE CartItems SET Quantity = %s WHERE CartItemID = %s;", (new_qty, existing['cartitemid']))
        else:
            if quantity > product['stockquantity']: return False, "Không đủ hàng tồn kho", None
            cursor.execute("INSERT INTO CartItems (CartID, ProductID, Quantity) VALUES (%s, %s, %s);", (cart_id, product_id, quantity))
            
        conn.commit()
        return True, "Đã thêm vào giỏ hàng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def update_item_qty(user_id, item_id, quantity):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cart_id = _get_or_create_cart(cursor, user_id)
        
        cursor.execute("SELECT ProductID FROM CartItems WHERE CartItemID = %s AND CartID = %s;", (item_id, cart_id))
        item = cursor.fetchone()
        if not item: return False, "Item không tồn tại trong giỏ của bạn", None
            
        if quantity <= 0:
            cursor.execute("DELETE FROM CartItems WHERE CartItemID = %s;", (item_id,))
        else:
            cursor.execute("SELECT StockQuantity FROM Products WHERE ProductID = %s;", (item['productid'],))
            stock = cursor.fetchone()['stockquantity']
            if quantity > stock: return False, "Vượt quá tồn kho", None
            cursor.execute("UPDATE CartItems SET Quantity = %s WHERE CartItemID = %s;", (quantity, item_id))
            
        conn.commit()
        return True, "Đã cập nhật số lượng", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def delete_item(user_id, item_id):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None
    try:
        cursor = conn.cursor()
        cart_id = _get_or_create_cart(cursor, user_id)
        cursor.execute("DELETE FROM CartItems WHERE CartItemID = %s AND CartID = %s RETURNING CartItemID;", (item_id, cart_id))
        if not cursor.fetchone(): return False, "Item không tồn tại", None
        conn.commit()
        return True, "Đã xóa sản phẩm", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()
