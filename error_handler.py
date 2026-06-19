from flask import jsonify, request

def success_response(message, data=None):
    """Trả về chuẩn JSON khi thành công"""
    return {"status": "success", "message": message, "data": data}

def error_response(message, status_code=400):
    """Trả về chuẩn JSON khi người dùng nhập sai, dùng jsonify để bọc lại"""
    return jsonify({"status": "error", "message": message, "data": None}), status_code

def server_error_response(e):
    """Bắt mọi lỗi code sập server, cấm tuyệt đối văng HTML"""
    print(f"❌ Lỗi Server nghiêm trọng: {str(e)}")
    return jsonify({"status": "error", "message": "Hệ thống đang bảo trì hoặc có lỗi nội bộ, vui lòng thử lại sau!", "data": None}), 500

def get_clean_json():
    """
    Hàm tiện ích quét toàn bộ Request JSON đầu vào từ Frontend/Postman,
    tự động chuyển tất cả các KEY về dạng CHỮ THƯỜNG.
    Giúp BE hoàn toàn lì đòn trước việc bất nhất quán hoa/thường (Ví dụ: Email vs email)
    """
    data = request.get_json()
    if not data:
        return {}
    # Dùng Dictionary Comprehension để lowercase toàn bộ key
    return {str(k).lower(): v for k, v in data.items()}