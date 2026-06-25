# import eventlet
# eventlet.monkey_patch(socket=False) # Lệnh cấm: "Hãy bất đồng bộ mọi thứ, TRỪ CỔNG MẠNG RA để tao còn gửi Email!"

from flask import Flask, jsonify, request
from flask_cors import CORS

# Thêm import thư viện JWT
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt, decode_token

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
@jwt_required(optional=True)
def api_get_all_shops():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        if page < 1: page = 1
        if limit < 1: limit = 10

        claims = get_jwt()
        role_name = claims.get('rolename') if claims else None

        is_success, message, result = get_all_shops(page, limit, role_name)
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
    
@app.route('/api/shops/<string:shop_id>', methods=['GET'])
@jwt_required(optional=True)
def api_get_shop_details(shop_id):
    try:
        claims = get_jwt()
        role_name = claims.get('rolename') if claims else None

        is_success, message, result_data = get_shop_details(str(shop_id).strip(), role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404 if "Không tìm thấy" in message else 400)
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
        
        if is_success:
            from flask_jwt_extended import create_access_token
            # [HOÀN TOÀN ĐỘNG]: Sử dụng vai trò thực tế từ DB dội ngược lên để cấp Token mới
            # Triệt tiêu vĩnh viễn lỗi giáng chức Admin khi tạo Shop!
            new_vip_token = create_access_token(
                identity=str(manager_id), 
                additional_claims={
                    "roleid": result_data['final_role_uuid'],
                    "rolename": result_data['final_role_name']
                }
            )

            response_payload = {
                "status": "success",
                "message": message,
                "data": result_data['shop'],
                "new_access_token": new_vip_token 
            }
            return jsonify(response_payload), 201 

        return error_response(message, 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops/<string:shop_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def api_update_shop(shop_id):
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi thông tin cần cập nhật", 400)

        user_id = get_jwt_identity()
        # [SO QUYỀN ĐỘNG]: Bốc RoleName ra dùng, không đọ UUID nữa!
        role_name = get_jwt().get('rolename')

        shop_name = data.get('shopname')
        address = data.get('address')
        hotline = data.get('hotline')
        description = data.get('description') 

        is_success, message, result_data = update_shop(str(shop_id).strip(), user_id, role_name, shop_name, address, hotline, description)
        
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404) 
    except Exception as e: return server_error_response(e)
    
@app.route('/api/shops/<string:shop_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_shop_status(shop_id):
    try:
        claims = get_jwt()
        if claims.get('rolename') != 'Admin':
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        is_success, message, result_data = toggle_shop_status(str(shop_id).strip())
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404)
    except Exception as e: return server_error_response(e)
    
# ================= MODULE CATEGORIES =================

@app.route('/api/categories', methods=['GET'])
@jwt_required(optional=True) # <--- SIÊU KỸ THUẬT: Khách vãng lai không có JWT cũng lọt, Admin có JWT cũng lọt!
def api_get_all_categories():
    try:
        claims = get_jwt()
        # Bốc rolename nếu người gọi có đeo thẻ JWT, nếu không đeo thẻ thì trả về None
        role_name = claims.get('rolename') if claims else None

        is_success, message, result_data = get_all_categories(role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/categories', methods=['POST'])
@jwt_required()
def api_create_category():
    try:
        # [RBAC ĐỘNG]: So RoleName thuần túy, chia tay roleid!
        if get_jwt().get('rolename') != 'Admin':
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
    
# [CHUẨN UUID]: Đổi <int:category_id> thành <string:category_id>
@app.route('/api/categories/<string:category_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def api_update_category(category_id):
    try:
        if get_jwt().get('rolename') != 'Admin':
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi thông tin cần cập nhật", 400)

        category_name = data.get('categoryname')
        description = data.get('description')

        if category_name is not None: category_name = category_name.strip()
        if description is not None: description = description.strip()

        is_success, message, result_data = update_category(str(category_id).strip(), category_name, description)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 400 if "định dạng" in message else 404)
    except Exception as e: return server_error_response(e)

@app.route('/api/categories/<string:category_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_category_status(category_id):
    try:
        if get_jwt().get('rolename') != 'Admin':
            return error_response("Bạn không có quyền thực hiện hành động này (Yêu cầu quyền Admin)", 403)

        is_success, message, result_data = toggle_category_status(str(category_id).strip())
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 400 if "định dạng" in message else 404)
    except Exception as e: return server_error_response(e)
    

# ================= MODULE PRODUCTS =================

@app.route('/api/products', methods=['GET'])
@jwt_required(optional=True) # <--- Thần chú: Khách vãng lai và Admin đều lọt
def api_get_all_products():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        if page < 1: page = 1
        if limit < 1: limit = 10

        claims = get_jwt()
        role_name = claims.get('rolename') if claims else None

        is_success, message, result = get_all_products(page, limit, role_name)
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

@app.route('/api/products/<string:product_id>', methods=['GET'])
@jwt_required(optional=True)
def api_get_product_details(product_id):
    try:
        claims = get_jwt()
        role_name = claims.get('rolename') if claims else None

        is_success, message, result_data = get_product_details(str(product_id).strip(), role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 404 if "Không tìm thấy" in message else 400)
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

        user_id = get_jwt_identity()
        # [SO QUYỀN ĐỘNG]: Bốc RoleName ra dùng, dẹp bỏ việc soi roleid!
        role_name = get_jwt().get('rolename')

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

        # Truyền role_name xuống Service
        is_success, message, result_data = create_product(
            product_name, price, stock_quantity, category_id, shop_id, user_id, role_name, image_urls
        )
        
        if is_success: return jsonify(success_response(message, result_data)), 201
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/products/<string:product_id>', methods=['PATCH', 'PUT'])
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

        user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        product_name = form_data.get('productname')
        if product_name == "": product_name = None
        
        # [VÁ TỰ SÁT ÉP KIỂU]: Tuyệt đối cấm bọc int() cho chuỗi UUID
        category_id_raw = form_data.get('categoryid')
        category_id = category_id_raw.strip() if category_id_raw and category_id_raw != "" else None
        
        price_raw = form_data.get('price')
        price = float(price_raw) if price_raw and price_raw != "" else None
        stock_raw = form_data.get('stockquantity')
        stock_quantity = int(stock_raw) if stock_raw and stock_raw != "" else None

        image_urls = []
        for file in danh_sach_files:
            if file.filename != '':
                url = upload_image(file)
                if url: image_urls.append(url)

        is_success, message, result_data = update_product(
            str(product_id).strip(), user_id, role_name, product_name, price, stock_quantity, category_id, image_urls
        )
        
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except ValueError: return error_response("Dữ liệu số không hợp lệ", 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/products/<string:product_id>', methods=['DELETE', 'PATCH'])
@jwt_required()
def api_toggle_product(product_id):
    try:
        user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = toggle_product_status(str(product_id).strip(), user_id, role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/products/<string:product_id>/ratings', methods=['POST'])
@jwt_required()
def api_submit_product_review(product_id):
    try:
        data = get_clean_json()
        if not data: return error_response("Vui lòng gửi dữ liệu đánh giá", 400)
            
        rating_raw = data.get('rating')
        review_text = data.get('reviewtext', '') 
        user_id = get_jwt_identity() 
        
        try:
            rating = int(rating_raw)
            if rating < 1 or rating > 5: return error_response("Điểm đánh giá phải từ 1 đến 5", 400)
        except (ValueError, TypeError):
            return error_response("Định dạng số sao không hợp lệ", 400)

        is_success, message, result_data = submit_product_review(str(product_id).strip(), user_id, rating, review_text)
        if is_success: return jsonify(success_response(message, result_data)), 201 
        return error_response(message, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/products/<string:product_id>/ratings/stats', methods=['GET'])
def api_get_product_rating_stats(product_id):
    try:
        is_success, message, result_data = get_product_rating_stats(str(product_id).strip())
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
        # [SO QUYỀN ĐỘNG]: Bốc RoleName ra dùng, chia tay roleid!
        role_name = get_jwt().get('rolename')

        is_success, message, result = get_all_orders(page, limit, user_id, role_name)
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
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = get_order_details(str(order_id).strip(), user_id, role_name)
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
        # [VÁ QUẢ BOM ÉP KIỂU]: Lấy string thuần, tuyệt đối không bọc int()
        shop_id = str(data.get('shopid')).strip()
        shipping_address = data.get('shippingaddress')
        payment_method = data.get('paymentmethod', 'COD') 
        items_raw = data.get('items', [])

        if not data.get('shopid') or not shipping_address or not items_raw:
            return error_response("Vui lòng điền đầy đủ UserID, ShopID, Địa chỉ và Danh sách món", 400)
            
        if len(items_raw) == 0: return error_response("Giỏ hàng đang trống", 400)

        items_list = []
        try:
            for item in items_raw:
                p_id = item.get('ProductID') or item.get('productid')
                qty = item.get('Quantity') or item.get('quantity')
                if not p_id or qty is None: raise ValueError
                
                # SỬA CHUẨN: ProductID giữ nguyên string, chỉ ép int(Quantity)
                items_list.append({'ProductID': str(p_id).strip(), 'Quantity': int(qty)})
        except ValueError: 
            return error_response("Định dạng món hàng hoặc số lượng không hợp lệ", 400)

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
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = update_order_status(str(order_id).strip(), new_status, user_id, role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/orders/<string:order_id>', methods=['DELETE'])
@jwt_required()
def api_cancel_order(order_id):
    try:
        user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = cancel_order(str(order_id).strip(), user_id, role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
@app.route('/api/orders/<string:order_id>/payment', methods=['GET'])
@jwt_required()
def api_get_order_payment_status(order_id):
    try:
        user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = get_order_payment_status(str(order_id).strip(), user_id, role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 404)
    except Exception as e: return server_error_response(e)

@app.route('/api/orders/<string:order_id>/payment', methods=['PATCH', 'PUT'])
@jwt_required()
def api_confirm_mock_payment(order_id):
    try:
        user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        is_success, message, result_data = confirm_mock_payment(str(order_id).strip(), user_id, role_name)
        if is_success: return jsonify(success_response(message, result_data)), 200
        return error_response(message, 403 if "quyền" in message else 400)
    except Exception as e: return server_error_response(e)
    
# ================= MODULE USERS & ROLES =================

@app.route('/api/roles', methods=['GET'])
@jwt_required()
def api_get_roles():
    try:
        claims = get_jwt()
        # SO CHUỖI ĐỘNG: Bốc rolename ra soi, chia tay vĩnh viễn việc đọ UUID!
        if claims.get('rolename') != 'Admin':
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
        claims = get_jwt()
        if claims.get('rolename') != 'Admin':
            return error_response("Bạn không có quyền thực hiện hành động này", 403)

        data = get_clean_json()
        role_id = data.get('roleid') if data else None
        if not role_id: return error_response("Vui lòng truyền RoleID", 400)
        
        # Truyền chuỗi string thuần xuống tầng Service
        is_success, msg, result = assign_role(str(user_id).strip(), str(role_id).strip())
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 404 if "Không tìm thấy" in msg else 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users', methods=['GET'])
@jwt_required()
def api_get_users():
    try:
        claims = get_jwt()
        if claims.get('rolename') != 'Admin':
            return error_response("Bạn không có quyền xem danh sách người dùng", 403)

        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        if page < 1: page = 1
        if limit < 1: limit = 10

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
@jwt_required()
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
            file_avatar = request.files.get('avatar_file')

        user_id = get_jwt_identity()
        
        full_name = form_data.get('fullname')
        if full_name == "": full_name = None
        
        address = form_data.get('address')
        if address == "": address = None
        
        # [BỌC THÉP TẤT CẢ CÁC TRƯỜNG MỚI]
        phone = form_data.get('phone') or form_data.get('phonenumber')
        if phone == "": phone = None
        
        gender = form_data.get('gender')
        if gender == "": gender = None
        
        birthday = form_data.get('birthday')
        if birthday == "": birthday = None

        avatar_url = upload_image(file_avatar) if file_avatar else None

        # [GỌI SERVICE VỚI ĐỦ BỘ PARAMETER]
        is_success, msg, result = update_profile(user_id, full_name, phone, address, gender, birthday, avatar_url)
        
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 400)
    except Exception as e:
        return server_error_response(e)

@app.route('/api/users/<string:user_id>/status', methods=['PATCH'])
@jwt_required()
def api_toggle_user_status(user_id):
    try:
        claims = get_jwt()
        if claims.get('rolename') != 'Admin':
            return error_response("Bạn không có quyền khóa tài khoản", 403)

        is_success, msg, result = toggle_user_status(str(user_id).strip())
        if is_success: return jsonify(success_response(msg, result)), 200
        return error_response(msg, 404)
    except Exception as e:
        return server_error_response(e)

# ================= MODULE REVENUE & STATS =================

@app.route('/api/revenue/total', methods=['GET'])
@jwt_required()
def api_get_total_revenue():
    try:
        claims = get_jwt()
        role_name = claims.get('rolename')
        user_id = get_jwt_identity()
        
        # [RBAC ĐỘNG]: Chia tay roleid [1, 2]
        if role_name not in ['Admin', 'Manager']:
            return error_response("Bạn không có quyền xem thống kê tài chính", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date định dạng YYYY-MM-DD", 400)
            
        is_success, msg, data = get_total_revenue(start_date.strip(), end_date.strip(), user_id, role_name)
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
        claims = get_jwt()
        role_name = claims.get('rolename')
        user_id = get_jwt_identity()

        if role_name not in ['Admin', 'Manager']:
            return error_response("Bạn không có quyền xem thống kê", 403)

        limit = request.args.get('limit', 10, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        is_success, msg, data = get_top_products(
            limit, 
            start_date.strip() if start_date else None, 
            end_date.strip() if end_date else None, 
            user_id, 
            role_name
        )
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/orders/status-breakdown', methods=['GET'])
@jwt_required()
def api_get_order_status_breakdown():
    try:
        claims = get_jwt()
        role_name = claims.get('rolename')
        user_id = get_jwt_identity()

        if role_name not in ['Admin', 'Manager']:
            return error_response("Bạn không có quyền xem thống kê", 403)

        is_success, msg, data = get_order_status_breakdown(user_id, role_name)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/revenue/by-shop', methods=['GET'])
@jwt_required()
def api_get_revenue_by_shop():
    try:
        claims = get_jwt()
        role_name = claims.get('rolename')
        user_id = get_jwt_identity()

        if role_name not in ['Admin', 'Manager']:
            return error_response("Bạn không có quyền xem thống kê", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date (YYYY-MM-DD)", 400)
            
        is_success, msg, data = get_revenue_by_shop(start_date.strip(), end_date.strip(), user_id, role_name)
        if is_success: return jsonify(success_response(msg, data)), 200
        return error_response(msg, 400)
    except Exception as e: return server_error_response(e)

@app.route('/api/stats/revenue/by-category', methods=['GET'])
@jwt_required()
def api_get_revenue_by_category():
    try:
        claims = get_jwt()
        role_name = claims.get('rolename')
        user_id = get_jwt_identity()

        if role_name not in ['Admin', 'Manager']:
            return error_response("Bạn không có quyền xem thống kê", 403)

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            return error_response("Vui lòng cung cấp start_date và end_date", 400)
            
        is_success, msg, data = get_revenue_by_category(start_date.strip(), end_date.strip(), user_id, role_name)
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
        
        if not user_id_param or not shop_id_raw: 
            return error_response("Vui lòng truyền đủ user_id và shop_id", 400)

        token_user_id = get_jwt_identity()
        role_name = get_jwt().get('rolename')

        # [RBAC ĐỘNG]: Khách hàng cấm xem trộm chat của người khác
        if role_name == 'Customer' and str(user_id_param).strip() != str(token_user_id):
            return error_response("Bạn không có quyền xem lịch sử hội thoại này", 403)

        is_success, msg, data = get_chat_history(
            str(user_id_param).strip(), 
            str(shop_id_raw).strip(), 
            token_user_id, 
            role_name
        )
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
        role_name = get_jwt().get('rolename')
        
        shop_id_str = form_data.get('shopid')
        target_user_id = form_data.get('userid') 
        content = form_data.get('content', '') 

        # [RBAC ĐỘNG]
        if role_name == 'Customer':
            sender_role = 'User'
            chat_user_id = token_user_id 
        else:
            sender_role = 'Shop'
            chat_user_id = target_user_id 

        if not shop_id_str or not chat_user_id: 
            return error_response("Thiếu thông tin định danh Cửa hàng hoặc Khách hàng", 400)
        if content == "" and not file_image: 
            return error_response("Nội dung tin nhắn không được để trống", 400)

        image_url = upload_image(file_image) if file_image else None

        # Lưu Database
        is_success, msg, result = send_message(
            str(chat_user_id).strip(), 
            str(shop_id_str).strip(), 
            sender_role, 
            content, 
            image_url, 
            token_user_id, 
            role_name
        )
        
        if is_success: 
            # PHÉP THUẬT WS: Bắn realtime vào đúng kênh định danh chuỗi
            room_name = f"chat_{chat_user_id}_{shop_id_str}"
            socketio.emit('receive_message', result, room=room_name)
            return jsonify(success_response(msg, result)), 201
            
        return error_response(msg, 403 if "quyền" in msg else 400)
    except Exception as e: return server_error_response(e)

# --- BẢO MẬT KÊNH SOCKET.IO (AUTHENTICATED HANDSHAKE) ---
@socketio.on('join_chat')
def on_join_chat(data):
    """Kênh WS bọc thép: Khách hàng buộc phải trình Thẻ JWT trùng khớp mã ID mới được lọt phòng"""
    raw_token = data.get('token')
    user_id = data.get('user_id')
    shop_id = data.get('shop_id')
    
    if not raw_token or not user_id or not shop_id:
        return False

    try:
        # Giải mã Token ngay tại trạm gác Websocket
        decoded = decode_token(raw_token)
        caller_id = str(decoded.get('sub'))
        role_name = decoded.get('rolename')

        # KIỂM TOÁN AN NINH: Khách cấm chui vào phòng chat có user_id của thằng khác!
        if role_name == 'Customer' and caller_id != str(user_id):
            print(f"🚨 [CRITICAL WS ALERT]: Client {caller_id} cố tình nghe lén phòng chat của user {user_id}!")
            return False

        room_name = f"chat_{user_id}_{shop_id}"
        join_room(room_name)
        print(f"🔒 [WS SECURED]: Client {caller_id} ({role_name}) đã kết nối an toàn vào phòng: {room_name}")
        return True
    except Exception as e:
        print(f"❌ [WS REJECTED]: Token từ chối - {str(e)}")
        return False

# ================= ĐỘNG CƠ KHỞI CHẠY SERVER =================
if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
