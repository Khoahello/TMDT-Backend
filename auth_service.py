import psycopg2.extras
from data_manager import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime, timedelta
import os
from flask_jwt_extended import create_access_token

import urllib.request
import urllib.error
import requests # <--- Thư viện gọi HTTP siêu nhẹ có sẵn của Python
import json

def _get_role_uuid(conn, role_name):
    """Hàm nội bộ: Truy vấn động Database để bốc chính xác UUID của một Role theo Tên"""
    cursor = conn.cursor()
    cursor.execute("SELECT RoleID FROM Roles WHERE RoleName = %s", (role_name,))
    res = cursor.fetchone()
    cursor.close()
    if not res:
        raise ValueError(f"CRITICAL ERROR: Trong Database không tồn tại Role mang tên '{role_name}'!")
    return str(res[0])

def register_user(fullname, email, password, phone, address):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        email = email.lower().strip()
        
        # 1. TRUY VẤN ĐỘNG: Bốc UUID của Customer từ DB ra, dẹp bỏ mọi sự gán cứng!
        customer_role_uuid = _get_role_uuid(conn, 'Customer')

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        hashed_password = generate_password_hash(password)
        
        sql_query = """
            INSERT INTO Users (FullName, Email, PasswordHash, PhoneNumber, Address, RoleID) 
            VALUES (%s, %s, %s, %s, %s, %s) 
            RETURNING UserID, FullName, Email, PhoneNumber, Address, RoleID;
        """
        cursor.execute(sql_query, (fullname, email, hashed_password, phone, address, customer_role_uuid))
        new_user = cursor.fetchone()
        
        # Chuẩn hóa kiểu chuỗi cho JSON
        new_user['userid'] = str(new_user['userid'])
        new_user['roleid'] = str(new_user['roleid'])

        conn.commit()
        return True, "Đăng ký tài khoản thành công!", new_user
        
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        return False, "Email này đã được đăng ký", None
    except Exception as e:
        if conn: conn.rollback()
        print("Lỗi SQL Register:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None
    finally:
        if conn: conn.close()

def login_user(email, password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. TRUY VẤN THÔNG TIN USER CƠ BẢN
        sql_user = """
            SELECT u.UserID::text AS userid, u.FullName AS fullname, u.Email AS email, 
                   u.PhoneNumber AS phone, u.Address AS address, u.AvatarURL AS avatar,
                   u.PasswordHash, u.IsActive, u.RoleID::text AS roleid, r.RoleName AS rolename
            FROM Users u JOIN Roles r ON u.RoleID = r.RoleID 
            WHERE u.Email = %s;
        """
        cursor.execute(sql_user, (email.strip().lower(),))
        user = cursor.fetchone()
        
        if not user:
            return False, "Email đăng nhập không tồn tại trong hệ thống!", None
            
        if not user['isactive']:
            return False, "Tài khoản của bạn đang bị tạm khóa!", None
            
        # Kiểm tra mật khẩu (dùng werkzeug.security hay bcrypt của ông)
        from werkzeug.security import check_password_hash
        if not check_password_hash(user['passwordhash'], password):
            return False, "Mật khẩu không chính xác!", None

        # 2. TẠO PAYLOAD TRẢ VỀ CHO FRONTEND
        user_payload = {
            "userid": user['userid'],
            "fullname": user['fullname'],
            "email": user['email'],
            "phone": user['phone'],
            "address": user['address'],
            "avatar": user['avatar'],
            "roleid": user['roleid'],
            "rolename": user['rolename'],
            "shop": None  # Mặc định khách hàng thường sẽ không có shop
        }

        # 3. ⚡️ NGHIỆP VỤ THẦN THÁNH: NẾU LÀ MANAGER -> ĐI TÌM SHOP CỦA HỌ NẠP VÀO!
        if user['rolename'] == 'Manager':
            sql_shop = """
                SELECT ShopID::text AS shopid, ShopName AS shopname, 
                       ShopImageURL AS shopimage, Address AS shopaddress, IsActive AS isactive
                FROM Shops 
                WHERE ManagerID = %s AND IsActive = TRUE;
            """
            cursor.execute(sql_shop, (user['userid'],))
            owned_shop = cursor.fetchone()
            
            if owned_shop:
                user_payload['shop'] = dict(owned_shop)

        # 4. TẠO TOKEN JWT (Nạp cả rolename vào claim để các API sau dùng)
        from flask_jwt_extended import create_access_token
        access_token = create_access_token(
            identity=user['userid'],
            additional_claims={
                "roleid": user['roleid'],
                "rolename": user['rolename']
            }
        )

        return True, "Đăng nhập thành công!", {
            "access_token": access_token,
            "user": user_payload
        }
        
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi hệ thống: {str(e)}", None
    finally:
        if conn: conn.close()


def change_password(user_id, old_password, new_password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT PasswordHash FROM Users WHERE UserID = %s", (str(user_id),))
        user = cursor.fetchone()
        
        if not user: return False, "Người dùng không tồn tại", None
            
        saved_hash = user.get('passwordhash') or user.get('PasswordHash')
        if not check_password_hash(saved_hash, old_password):
            return False, "Mật khẩu hiện tại không đúng", None
            
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE Users SET PasswordHash = %s, UpdatedAt = CURRENT_TIMESTAMP WHERE UserID = %s", (new_hash, str(user_id)))
        conn.commit()
        return True, "Cập nhật mật khẩu mới thành công", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

import urllib.request
import urllib.error
import json
import os

# ================= HÀM GỬI MAIL BREVO GLOBAL BẰNG THƯ VIỆN LÕI =================
def send_otp_email(receiver_email, otp):
    """Bắn mail qua cổng REST API của Brevo bằng urllib. Miễn nhiễm 100% lỗi Gunicorn/Render."""
    api_key = os.getenv("BREVO_API_KEY")
    sender_mail = os.getenv("BREVO_SENDER_EMAIL")

    if not api_key or not sender_mail:
        print("⚠️ [BREVO ERROR]: Thiếu cấu hình BREVO_API_KEY hoặc BREVO_SENDER_EMAIL")
        return False

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; border: 1px solid #e2e8f0; border-radius: 20px; background-color: #ffffff; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
        <div style="text-align: center; margin-bottom: 25px;">
            <span style="font-size: 22px; font-weight: 900; color: #0f172a; letter-spacing: -0.5px;">TECH</span>
            <span style="font-size: 22px; font-weight: 900; color: #2563eb; letter-spacing: -0.5px;">TONIC</span>
            <p style="color: #64748b; font-size: 13px; margin-top: 5px; font-weight: 600;">HỆ THỐNG XÁC THỰC SÀN TMDT DUE</p>
        </div>
        
        <p style="color: #334155; font-size: 14px;">Xin chào,</p>
        <p style="color: #334155; font-size: 14px; line-height: 1.6;">Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu truy cập. Vui lòng nhập mã xác thực bảo mật dưới đây:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <div style="display: inline-block; font-size: 34px; font-weight: 900; letter-spacing: 10px; color: #2563eb; background-color: #f1f5f9; padding: 14px 32px; border-radius: 16px; border: 2px solid #cbd5e1;">
                {otp}
            </div>
        </div>
        
        <p style="color: #e11d48; font-size: 12px; text-align: center; font-weight: 700;">* Mã xác thực có hiệu lực trong 15 phút. Tuyệt đối không gửi cho bất kỳ ai.</p>
        <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 25px 0;" />
        <p style="color: #94a3b8; font-size: 11px; text-align: center; margin: 0;">Đại học Kinh tế Đà Nẵng (DUE) - Đồ án lập trình Backend.</p>
    </div>
    """

    payload = {
        "sender": {
            "name": "Sàn TMDT DUE",
            "email": sender_mail
        },
        "to": [{"email": receiver_email}],
        "subject": f"[{otp}] Mã xác thực khôi phục mật khẩu DUE",
        "htmlContent": html_content
    }

    try:
        # 1. Đóng gói dữ liệu thành dạng Bytes (yêu cầu bắt buộc của urllib)
        data_bytes = json.dumps(payload).encode('utf-8')
        
        # 2. Khởi tạo một Request tiêu chuẩn của Python lõi
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method='POST')
        
        # 3. Phóng gói tin đi và chờ phản hồi (timeout 10 giây để chống treo server)
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            if status_code in [200, 201, 202]:
                print(f"🎉 [BREVO DISPATCH SUCCESS]: Đã bắn OTP tới -> {receiver_email}")
                return True
            else:
                print(f"❌ [BREVO REJECTED]: HTTP Status {status_code}")
                return False

    except urllib.error.HTTPError as e:
        error_info = e.read().decode('utf-8')
        print(f"❌ [BREVO HTTP ERROR]: Code {e.code} - {error_info}")
        return False
    except Exception as e:
        print(f"❌ [BREVO SYSTEM EXCEPTION]: {str(e)}")
        return False

def forgot_password(email):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        email = email.lower().strip()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID FROM Users WHERE Email = %s", (email,))
        if not cursor.fetchone():
            return False, "Email không tồn tại trong hệ thống", None
            
        otp = str(random.randint(100000, 999999))
        expiry_time = datetime.now() + timedelta(minutes=15)
        
        cursor.execute("UPDATE Users SET ResetOTP = %s, OTPExpiry = %s WHERE Email = %s", (otp, expiry_time, email))
        conn.commit()
        
        mail_sent = send_otp_email(email, otp)
        
        if mail_sent:
            return True, f"Mã khôi phục đã được gửi đến email {email}. Vui lòng kiểm tra hộp thư.", None
        else:
            # ROLLBACK KHI GẶP SỰ CỐ: Xóa sạch OTP vừa tạo để giữ nguyên vẹn CSDL
            cursor.execute("UPDATE Users SET ResetOTP = NULL, OTPExpiry = NULL WHERE Email = %s", (email,))
            conn.commit()
            return False, "Hệ thống gửi email đang gặp rào cản kết nối mạng. Vui lòng thử lại sau.", None
            
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi hệ thống: {str(e)}", None
    finally:
        if conn: conn.close()

def verify_otp(email, otp):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        email = email.lower().strip()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT ResetOTP, OTPExpiry FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()
        
        if not user: return False, "Email không tồn tại", None
        
        saved_otp = user.get('resetotp') or user.get('ResetOTP')
        expiry = user.get('otpexpiry') or user.get('OTPExpiry')
        
        if not saved_otp or saved_otp != otp:
            return False, "Mã xác thực không hợp lệ", None
            
        if expiry < datetime.now():
            return False, "Mã xác thực đã hết hạn, vui lòng yêu cầu mã mới", None
            
        return True, "Mã xác thực hợp lệ. Vui lòng đặt mật khẩu mới.", None
    except Exception as e:
        return False, f"Lỗi kiểm tra OTP: {str(e)}", None
    finally:
        if conn: conn.close()

def reset_password(email, otp, new_password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        email = email.lower().strip()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT ResetOTP, OTPExpiry FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()
        
        if not user: return False, "Email không tồn tại", None
        
        saved_otp = user.get('resetotp') or user.get('ResetOTP')
        expiry = user.get('otpexpiry') or user.get('OTPExpiry')
        
        if saved_otp != otp:
            return False, "Mã OTP không hợp lệ", None
            
        if expiry < datetime.now():
            cursor.execute("UPDATE Users SET ResetOTP = NULL, OTPExpiry = NULL, UpdatedAt = CURRENT_TIMESTAMP WHERE Email = %s", (email,))
            conn.commit()
            return False, "Mã OTP đã hết hạn, vui lòng yêu cầu mã mới", None
            
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE Users SET PasswordHash = %s, ResetOTP = NULL, OTPExpiry = NULL, UpdatedAt = CURRENT_TIMESTAMP WHERE Email = %s", (new_hash, email))
        conn.commit()
        
        return True, "Đổi mật khẩu thành công! Vui lòng đăng nhập lại.", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi đặt lại mật khẩu: {str(e)}", None
    finally:
        if conn: conn.close()
