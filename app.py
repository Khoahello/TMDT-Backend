import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request
from flask_cors import CORS

# Thêm import thư viện JWT
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt

from flask_socketio import SocketIO, join_room, emit

import os
from dotenv import load_dotenv

from datetime import timedelta

# Lấy các chốt chặn xử lý JSON và báo lỗi
from error_handler import success_response, error_response, server_error_response, get_clean_json

from upload_service import upload_image

# Module Auth
from auth_service import register_user, login_user, change_password, verify_otp, forgot_password, reset_password

# Module Shops
from shops_service import get_all_shops, get_shop_details, create_shop, update_shop, toggle_shop_status

# Module Categories
from categories_service import get_all_categories, create_category, update_category, toggle_category_status

# Module Products
from products_service import get_all_products, get_product_details, create_product, update_product, toggle_product_status, submit_product_review, get_product_rating_stats

# Module Orders
from orders_service import get_all_orders, get_order_details, create_order, update_order_status, cancel_order, get_order_payment_status, confirm_mock_payment

# Module Users & Roles
from users_service import get_all_roles, assign_role, get_all_users, get_user_profile, update_profile, toggle_user_status

# Module Revenue & Stats
from stats_service import get_total_revenue, get_top_products, get_order_status_breakdown, get_revenue_by_shop, get_revenue_by_category

# Module Chat
from chat_service import get_chat_history, send_message

load_dotenv() # Load biến môi trường từ file .env

app = Flask(__name__)

# CORS giúp Frontend (port 3000) gọi API không bị chặn
CORS(app)

# Cấu hình "Chìa khóa vạn năng" cho JWT (Tuyệt đối không để lộ)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'chuoi_bi_mat_cua_ong_gia_123!@#')

# Ép thẻ sống lâu 30 ngày để test Postman không bị văng
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

jwt = JWTManager(app)

# KHỞI TẠO CỖ MÁY REAL-TIME (Hỗ trợ gọi chéo từ mọi Frontend)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================= MODULE AUTH =================
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    try:
        data = get_clean_json() # Ép toàn bộ Key về chữ thường
        if not data:
            return error_response("Vui lòng gửi dữ liệu", 400)

        # Tự tin dùng key chữ thường để lấy dữ liệu
        fullname = data.get('fullname')
        email = data.get('email')
        password = data.get('password')
        phone = data.get('phonenumber') or data.get('phone')
        address = data.get('address')

        if not fullname or not email or not password or not phone or not address:
            return error_response("Vui lòng điền đầy đủ tất cả thông tin (Tên, Email, Mật khẩu, SĐT, Địa chỉ)", 400)
            
        is_success, message, result_data = register_user(fullname, email, password, phone, address)
        
        if is_success:
            return jsonify(success_response(message, result_data)), 200
        else:
            return error_response(message, 400)
            
    except Exception as e:
        return server_error_response(e)

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    try:
        data = get_clean_json()
        if not data:
            return error_response("Vui lòng gửi dữ liệu", 400)

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return error_response("Vui lòng nhập Email và Mật khẩu", 400)
            
        is_success, message, result_data = login_user(email, password)
        
        if is_success:
            return jsonify(success_response(message, result_data)), 200
        else:
            return error_response(message, 400)
            
    except Exception as e:
        return server_error_response(e)
    
@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required() # <--- Yêu cầu bắt buộc phải có thẻ JWT
def api_change_password():
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu", 400)
        
        # --- BẢO MẬT TUYỆT ĐỐI ---
        # Bóc UserID trực tiếp từ thẻ JWT của người đang đăng nhập, không cần truyền Email nữa
        user_id = get_jwt_identity()
        
        # Đề phòng FE gửi old_password hoặc oldpassword
        old_password = data.get('old_password') or data.get('oldpassword')
        new_password = data.get('new_password') or data.get('newpassword')
        
        if not old_password or not new_password:
            return error_response("Thiếu thông tin mật khẩu cũ hoặc mật khẩu mới", 400)
            
        # Truyền user_id xuống Tầng Service
        is_success, msg, _ = change_password(user_id, old_password, new_password)
        
        return jsonify(success_response(msg)) if is_success else error_response(msg, 400)
        
    except Exception as e: 
        return server_error_response(e)

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    try:
        data = get_clean_json()
        email = data.get('email')
        if not email: return error_response("Vui lòng nhập Email", 400)
        
        is_success, msg, _ = forgot_password(email)
        return jsonify(success_response(msg)) if is_success else error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/auth/verify-otp', methods=['POST'])
def api_verify_otp():
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu", 400)
        
        email = data.get('email')
        otp = data.get('otp')
        
        if not email or not otp:
            return error_response("Vui lòng điền đủ Email và Mã OTP", 400)
            
        is_success, msg, _ = verify_otp(email, otp)
        return jsonify(success_response(msg)) if is_success else error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu", 400)
        
        email = data.get('email')
        otp = data.get('otp')
        new_password = data.get('new_password') or data.get('newpassword')
        
        if not all([email, otp, new_password]):
            return error_response("Vui lòng điền đủ Email, Mã OTP và Mật khẩu mới", 400)
            
        is_success, msg, _ = reset_password(email, otp, new_password)
        return jsonify(success_response(msg)) if is_success else error_response(msg, 400)
    except Exception as e: return server_error_response(e)

# ================= MODULE SHOPS =================
@app.route('/api/shops', methods=['GET'])
def api_get_all_shops():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        if page < 1: page = 1
        if limit < 1: limit = 10

        is_success, message, result = get_all_shops(page, limit)
        
        if is_success:
            response_payload = {
                "status": "success", "message": message, "data": result["shops"],
                "pagination": {
                    "total_items": result["meta"]["total_items"],
                    "current_page": result["meta"]["current_page"],
                    "total_pages": result["meta"]["total_pages"]
                }
            }
            return jsonify(response_payload), 200
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops/<int:shop_id>', methods=['GET'])
def api_get_shop_details(shop_id):
    try:
        is_success, message, result_data = get_shop_details(shop_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops', methods=['POST'])
@jwt_required()
def api_create_shop():
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu", 400)

        shop_name = data.get('shopname')
        address = data.get('address')
        hotline = data.get('hotline')
        description = data.get('description')

        manager_id = get_jwt_identity()

        if not shop_name:
            return error_response("Vui lòng cung cấp Tên cửa hàng (ShopName)", 400)

        is_success, message, result_data = create_shop(shop_name, address, hotline, manager_id, description)
        if is_success: return jsonify(success_response(message, result_data)), 201 
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops/<int:shop_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def api_update_shop(shop_id):
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi thông tin cần cập nhật", 400)

        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        shop_name = data.get('shopname')
        address = data.get('address')
        hotline = data.get('hotline')
        description = data.get('description') # ĐÃ BỔ SUNG ĐỂ HỖ TRỢ UPDATE MÔ TẢ

        is_success, message, result_data = update_shop(shop_id, user_id, role_id, shop_name, address, hotline, description)
        
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404) 
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops/<int:shop_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_shop_status(shop_id):
    try:
        claims = get_jwt()
        if claims.get('roleid') != 1:
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        is_success, message, result_data = toggle_shop_status(shop_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    
# ================= MODULE CATEGORIES =================

@app.route('/api/categories', methods=['GET'])
def api_get_all_categories():
    try:
        is_success, message, result_data = get_all_categories()
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/categories', methods=['POST'])
@jwt_required()
def api_create_category():
    try:
        # BẢO MẬT: Chỉ Admin mới được quyền thêm danh mục
        if get_jwt().get('roleid') != 1:
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu", 400)

        category_name = data.get('categoryname')
        description = data.get('description')

        if category_name: category_name = category_name.strip()
        if description: description = description.strip()
        if description == "": description = None

        if not category_name:
            return error_response("Vui lòng cung cấp Tên danh mục hợp lệ", 400)
            
        is_success, message, result_data = create_category(category_name, description)
        if is_success: return jsonify(success_response(message, result_data)), 201
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/categories/<int:category_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def api_update_category(category_id):
    try:
        # BẢO MẬT: Chỉ Admin mới được sửa danh mục
        if get_jwt().get('roleid') != 1:
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi thông tin cần cập nhật", 400)

        category_name = data.get('categoryname')
        description = data.get('description')

        if category_name is not None: category_name = category_name.strip()
        if description is not None: description = description.strip()

        is_success, message, result_data = update_category(category_id, category_name, description)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)


@app.route('/api/categories/<int:category_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_category_status(category_id):
    try:
        # BẢO MẬT: Chỉ Admin mới được quyền Ẩn/Hiện danh mục
        if get_jwt().get('roleid') != 1:
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        is_success, message, result_data = toggle_category_status(category_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    

# ================= MODULE PRODUCTS =================

@app.route('/api/products', methods=['GET'])
def api_get_all_products():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        if page < 1: page = 1
        if limit < 1: limit = 10

        is_success, message, result = get_all_products(page, limit)
        if is_success:
            response_payload = {
                "status": "success", "message": message, "data": result["products"],
                "pagination": {
                    "total_items": result["meta"]["total_items"],
                    "current_page": result["meta"]["current_page"],
                    "total_pages": result["meta"]["total_pages"]
                }
            }
            return jsonify(response_payload), 200
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/products/<int:product_id>', methods=['GET'])
def api_get_product_details(product_id):
    try:
        is_success, message, result_data = get_product_details(product_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/products', methods=['POST'])
@jwt_required()
def api_create_product():
    try:
        form_data = {k.lower(): v.strip() for k, v in request.form.items()}
        
        product_name = form_data.get('productname')
        price_raw = form_data.get('price')
        stock_raw = form_data.get('stockquantity', '0')
        category_id = form_data.get('categoryid')
        shop_id = form_data.get('shopid')

        # BẢO MẬT: Bóc thông tin Token
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        if not product_name or not price_raw or not category_id or not shop_id:
            return error_response("Vui lòng điền đầy đủ Tên, Giá, Danh mục và Cửa hàng", 400)

        try:
            price = float(price_raw)
            stock_quantity = int(stock_raw)
            if price <= 0 or stock_quantity < 0:
                return error_response("Giá và Số lượng tồn kho không hợp lệ", 400)
        except ValueError:
            return error_response("Giá và Số lượng phải là định dạng số", 400)

        danh_sach_files = request.files.getlist('images')
        image_urls = []
        for file in danh_sach_files:
            if file.filename != '': 
                url = upload_image(file)
                if url: image_urls.append(url)

        # Truyền thêm user_id và role_id xuống Service
        is_success, message, result_data = create_product(
            product_name, price, stock_quantity, category_id, shop_id, user_id, role_id, image_urls
        )
        
        if is_success: return jsonify(success_response(message, result_data)), 201
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/products/<int:product_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def api_update_product(product_id):
    try:
        json_data = request.get_json() if request.is_json else None
        if json_data:
            form_data = {k.lower(): str(v).strip() for k, v in json_data.items() if v is not None}
            danh_sach_files = [] 
        else:
            form_data = {k.lower(): v.strip() for k, v in request.form.items()}
            danh_sach_files = request.files.getlist('images')

        # BẢO MẬT: Bóc thông tin Token
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        product_name = form_data.get('productname')
        if product_name == "": product_name = None
        category_id_raw = form_data.get('categoryid')
        category_id = int(category_id_raw) if category_id_raw and category_id_raw != "" else None
        price_raw = form_data.get('price')
        price = float(price_raw) if price_raw and price_raw != "" else None
        stock_raw = form_data.get('stockquantity')
        stock_quantity = int(stock_raw) if stock_raw and stock_raw != "" else None

        image_urls = []
        for file in danh_sach_files:
            if file.filename != '':
                url = upload_image(file)
                if url: image_urls.append(url)

        # Truyền thêm user_id và role_id xuống Service
        is_success, message, result_data = update_product(
            product_id, user_id, role_id, product_name, price, stock_quantity, category_id, image_urls
        )
        
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except ValueError: return error_response("Dữ liệu số không hợp lệ", 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/products/<int:product_id>', methods=['DELETE', 'PATCH'])
@jwt_required()
def api_toggle_product(product_id):
    try:
        # BẢO MẬT: Bóc thông tin Token
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = toggle_product_status(product_id, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/products/<int:product_id>/ratings', methods=['POST'])
@jwt_required()
def api_submit_product_review(product_id):
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu đánh giá", 400)
            
        rating_raw = data.get('rating')
        review_text = data.get('reviewtext', '') # THÊM NỘI DUNG ĐÁNH GIÁ
        user_id = get_jwt_identity() 
        
        try:
            rating = int(rating_raw)
            if rating < 1 or rating > 5: return error_response("Điểm đánh giá phải từ 1 đến 5", 400)
        except (ValueError, TypeError):
            return error_response("Định dạng số sao không hợp lệ", 400)

        # Truyền thêm review_text
        is_success, message, result_data = submit_product_review(product_id, user_id, rating, review_text)
        if is_success: return jsonify(success_response(message, result_data)), 201 
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/products/<int:product_id>/ratings/stats', methods=['GET'])
def api_get_product_rating_stats(product_id):
    try:
        is_success, message, result_data = get_product_rating_stats(product_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    

# ================= MODULE ORDERS =================

@app.route('/api/orders', methods=['GET'])
@jwt_required()
def api_get_all_orders():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        if page < 1: page = 1
        if limit < 1: limit = 10

        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result = get_all_orders(page, limit, user_id, role_id)
        if is_success:
            return jsonify({
                "status": "success", "message": message, "data": result["orders"],
                "pagination": {
                    "total_items": result["meta"]["total_items"],
                    "current_page": result["meta"]["current_page"],
                    "total_pages": result["meta"]["total_pages"]
                }
            }), 200
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/orders/<string:order_id>', methods=['GET'])
@jwt_required()
def api_get_order_details(order_id):
    try:
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = get_order_details(order_id, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/orders', methods=['POST'])
@jwt_required()
def api_create_order():
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng cung cấp dữ liệu đơn hàng", 400)

        user_id = get_jwt_identity()
        shop_id_raw = data.get('shopid')
        shipping_address = data.get('shippingaddress')
        payment_method = data.get('paymentmethod', 'COD') 
        items_raw = data.get('items', [])

        if not shop_id_raw or not shipping_address or not items_raw:
            return error_response("Vui lòng điền đầy đủ UserID, ShopID, Địa chỉ và Danh sách món", 400)
            
        try: shop_id = int(shop_id_raw)
        except ValueError: return error_response("ShopID phải là định dạng số", 400)
            
        if len(items_raw) == 0: return error_response("Giỏ hàng đang trống", 400)

        items_list = []
        try:
            for item in items_raw:
                p_id = item.get('ProductID') or item.get('productid')
                qty = item.get('Quantity') or item.get('quantity')
                if p_id is None or qty is None: raise ValueError
                items_list.append({'ProductID': int(p_id), 'Quantity': int(qty)})
        except ValueError: return error_response("Định dạng món hàng không hợp lệ", 400)

        is_success, message, result_data = create_order(user_id, shop_id, shipping_address, payment_method, items_list)
        if is_success: return jsonify(success_response(message, result_data)), 201
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/orders/<string:order_id>/status', methods=['PATCH', 'PUT'])
@jwt_required()
def api_update_order_status(order_id):
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng cung cấp trạng thái mới", 400)
            
        new_status = data.get('status')
        if not new_status: return error_response("Trường 'Status' không được để trống", 400)

        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = update_order_status(order_id, new_status, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/orders/<string:order_id>', methods=['DELETE'])
@jwt_required()
def api_cancel_order(order_id):
    try:
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = cancel_order(order_id, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/orders/<string:order_id>/payment', methods=['GET'])
@jwt_required()
def api_get_order_payment_status(order_id):
    try:
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = get_order_payment_status(order_id, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except Exception as e: return server_error_response(e)

@app.route('/api/orders/<string:order_id>/payment', methods=['PATCH', 'PUT'])
@jwt_required()
def api_confirm_mock_payment(order_id):
    try:
        user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        is_success, message, result_data = confirm_mock_payment(order_id, user_id, role_id)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
# ================= MODULE USERS & ROLES=================

@app.route('/api/roles', methods=['GET'])
@jwt_required()
def api_get_roles():
    try:
        # BẢO MẬT: Chỉ Admin (RoleID = 1) mới được xem danh sách quyền
        claims = get_jwt()
        if claims.get('roleid') != 1:
            return error_response("Bạn không có quyền truy cập (Yêu cầu quyền Admin)", 403)

        is_success, msg, data = get_all_roles()
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users/<string:user_id>/role', methods=['PATCH'])
@jwt_required()
def api_assign_role(user_id):
    try:
        # BẢO MẬT: Chỉ Admin mới được phân quyền cho người khác
        claims = get_jwt()
        if claims.get('roleid') != 1:
            return error_response("Bạn không có quyền thực hiện hành động này", 403)

        data = get_clean_json()
        role_id = data.get('roleid') if data else None
        if not role_id: return error_response("Vui lòng truyền RoleID", 400)
        
        is_success, msg, result = assign_role(user_id, int(role_id))
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 404)
    except ValueError:
        return error_response("RoleID phải là số nguyên", 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users', methods=['GET'])
@jwt_required()
def api_get_users():
    try:
        # BẢO MẬT: Chỉ Admin mới được xem toàn bộ danh sách khách hàng của sàn
        claims = get_jwt()
        if claims.get('roleid') != 1:
            return error_response("Bạn không có quyền xem danh sách người dùng", 403)

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        is_success, msg, result = get_all_users(page, limit)
        if is_success:
            return jsonify({
                "status": "success", "message": msg,
                "data": result["users"], "pagination": result["meta"]
            }), 200
        return error_response(msg, 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users/profile', methods=['GET'])
@jwt_required() # <--- Yêu cầu phải có Token
def api_get_my_profile():
    try:
        user_id = get_jwt_identity()
        
        is_success, msg, result = get_user_profile(user_id)
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 404)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users/profile', methods=['PATCH', 'PUT'])
@jwt_required()
def api_update_profile():
    try:
        if request.is_json:
            form_data = {k.lower(): str(v).strip() for k, v in request.get_json().items() if v is not None}
            file_avatar = None
        else:
            form_data = {k.lower(): v.strip() for k, v in request.form.items()}
            file_avatar = request.files.get('avatar_file') # Tên field theo frontend/postman

        # Bóc Token để lấy UserID, Hacker không thể sửa mã ID này được
        user_id = get_jwt_identity()
        
        full_name = form_data.get('fullname')
        if full_name == "": full_name = None
        address = form_data.get('address')
        if address == "": address = None

        avatar_url = upload_image(file_avatar)

        is_success, msg, result = update_profile(user_id, full_name, address, avatar_url)
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users/<string:user_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_user_status(user_id):
    try:
        # BẢO MẬT: Chỉ Admin mới có quyền khóa/mở khóa tài khoản
        claims = get_jwt()
        if claims.get('roleid') != 1:
            return error_response("Bạn không có quyền khóa tài khoản", 403)

        is_success, msg, result = toggle_user_status(user_id)
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 404)
    except Exception as e:
        return server_error_response(e)

# ================= MODULE REVENUE & STATS =================

@app.route('/api/revenue/total', methods=['GET'])
@jwt_required()
def api_get_total_revenue():
    try:
        # BẢO MẬT: Admin (1) và Manager (2) được phép truy cập
        role_id = get_jwt().get('roleid')
        user_id = get_jwt_identity()
        if role_id not in [1, 2]:
            return error_response("Bạn không có quyền xem thống kê tài chính", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date (YYYY-MM-DD)", 400)
            
        is_success, msg, data = get_total_revenue(start_date, end_date, user_id, role_id)
        if is_success:
            return jsonify({
                "status": "success", "message": msg,
                "data": {"Period": f"{start_date} đến {end_date}", **data}
            }), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/revenue/top-products', methods=['GET'])
@app.route('/api/stats/revenue/by-product', methods=['GET']) 
@jwt_required()
def api_get_top_products():
    try:
        role_id = get_jwt().get('roleid')
        user_id = get_jwt_identity()
        if role_id not in [1, 2]:
            return error_response("Bạn không có quyền xem thống kê", 403)

        limit = request.args.get('limit', 10, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        is_success, msg, data = get_top_products(limit, start_date, end_date, user_id, role_id)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/orders/status-breakdown', methods=['GET'])
@jwt_required()
def api_get_order_status_breakdown():
    try:
        role_id = get_jwt().get('roleid')
        user_id = get_jwt_identity()
        if role_id not in [1, 2]:
            return error_response("Bạn không có quyền xem thống kê", 403)

        is_success, msg, data = get_order_status_breakdown(user_id, role_id)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/revenue/by-shop', methods=['GET'])
@jwt_required()
def api_get_revenue_by_shop():
    try:
        role_id = get_jwt().get('roleid')
        user_id = get_jwt_identity()
        if role_id not in [1, 2]:
            return error_response("Bạn không có quyền xem thống kê", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date", 400)
            
        is_success, msg, data = get_revenue_by_shop(start_date, end_date, user_id, role_id)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/revenue/by-category', methods=['GET'])
@jwt_required()
def api_get_revenue_by_category():
    try:
        role_id = get_jwt().get('roleid')
        user_id = get_jwt_identity()
        if role_id not in [1, 2]:
            return error_response("Bạn không có quyền xem thống kê", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date", 400)
            
        is_success, msg, data = get_revenue_by_category(start_date, end_date, user_id, role_id)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)
    
# ================= MODULE CHAT & REAL-TIME SOCKET =================

@app.route('/api/chat/history', methods=['GET'])
@jwt_required()
def api_get_chat_history():
    try:
        user_id_param = request.args.get('user_id')
        shop_id_raw = request.args.get('shop_id')
        if not user_id_param or not shop_id_raw: return error_response("Vui lòng truyền user_id và shop_id", 400)
        try: shop_id = int(shop_id_raw)
        except ValueError: return error_response("ShopID phải định dạng số", 400)

        token_user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')

        if role_id == 3 and str(user_id_param) != str(token_user_id):
            return error_response("Bạn không có quyền xem", 403)

        is_success, msg, data = get_chat_history(user_id_param, shop_id, token_user_id, role_id)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 403 if "quyền" in msg else 400)
    except Exception as e: return server_error_response(e)


@app.route('/api/chat/send', methods=['POST'])
@jwt_required()
def api_send_message():
    try:
        if request.is_json:
            form_data = {k.lower(): str(v).strip() for k, v in request.get_json().items() if v is not None}
            file_image = None
        else:
            form_data = {k.lower(): v.strip() for k, v in request.form.items()}
            file_image = request.files.get('image_file')

        token_user_id = get_jwt_identity()
        role_id = get_jwt().get('roleid')
        
        shop_id_raw = form_data.get('shopid')
        target_user_id = form_data.get('userid') 
        content = form_data.get('content', '') 

        if role_id == 3:
            sender_role = 'User'
            chat_user_id = token_user_id 
        else:
            sender_role = 'Shop'
            chat_user_id = target_user_id 

        if not shop_id_raw or not chat_user_id: return error_response("Thiếu thông tin", 400)
        if content == "" and not file_image: return error_response("Tin nhắn trống", 400)
        try: shop_id = int(shop_id_raw)
        except ValueError: return error_response("ShopID phải là số", 400)

        image_url = upload_image(file_image) if file_image else None

        # Lưu tin nhắn vào Database
        is_success, msg, result = send_message(chat_user_id, shop_id, sender_role, content, image_url, token_user_id, role_id)
        
        if is_success: 
            # BƯỚC PHÉP THUẬT: Phát tin nhắn qua Socket.IO vào đúng phòng của 2 người
            room_name = f"chat_{chat_user_id}_{shop_id}"
            socketio.emit('receive_message', result, room=room_name)
            return jsonify(success_response(msg, result)), 201
            
        return error_response(msg, 403 if "quyền" in msg else 400)
    except Exception as e: return server_error_response(e)

# --- KHAI BÁO CÁC KÊNH LẮNG NGHE CỦA SOCKET.IO ---
@socketio.on('join_chat')
def on_join_chat(data):
    """Frontend gọi cái này khi mở khung chat để chui vào phòng"""
    user_id = data.get('user_id')
    shop_id = data.get('shop_id')
    if user_id and shop_id:
        room_name = f"chat_{user_id}_{shop_id}"
        join_room(room_name)
        print(f"🔗 Đã thiết lập kết nối Real-time cho phòng: {room_name}")

# ================= ĐỘNG CƠ KHỞI CHẠY SERVER =================
if __name__ == '__main__':
    # XÓA APP.RUN CŨ ĐI! Bắt buộc dùng socketio.run để server gánh được cả API và Real-time
    socketio.run(app, debug=True, port=5000)
