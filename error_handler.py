from flask import jsonify, request

def success_response(message, data=None):
    """BỌC THÉP NGOẠI GIAO: Trả về đồng thời 'status' và 'success' để tương thích mọi phiên bản code FE"""
    return {
        "status": "success", 
        "success": True, 
        "message": message, 
        "data": data
    }

def error_response(message, status_code=400):
    return jsonify({
        "status": "error", 
        "success": False, 
        "message": message, 
        "data": None
    }), status_code

def server_error_response(e):
    print(f"❌ [CRITICAL SERVER ERROR]: {str(e)}")
    return jsonify({
        "status": "error", 
        "success": False,
        "message": "Hệ thống máy chủ gặp sự cố nội bộ. Vui lòng thử lại sau!", 
        "data": None
    }), 500

def get_clean_json():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return {}
    return {str(k).lower(): v for k, v in data.items()}