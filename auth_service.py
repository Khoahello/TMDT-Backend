import psycopg2.extras
from data_manager import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime, timedelta
import os
from flask_jwt_extended import create_access_token, decode_token

import urllib.request
import urllib.error
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


def request_register_otp(email):
    """BƯỚC 1: Khách chỉ nhập Email -> Kiểm tra DB -> Bắn OTP -> Trả về step1_token"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        email = email.lower().strip()
        cursor = conn.cursor()
        
        cursor.execute("SELECT UserID FROM Users WHERE Email = %s;", (email,))
        if cursor.fetchone():
            return False, "Email này đã được sử dụng trên hệ thống!", None
            
        otp = str(random.randint(100000, 999999))
        mail_sent = send_otp_email(email, otp, email_type="register")
        if not mail_sent:
            return False, "Hệ thống Mail đang gặp sự cố, vui lòng thử lại sau!", None

        # Bọc email và OTP vào thẻ tạm (15 phút)
        temp_payload = {"email": email, "otp": otp, "purpose": "reg_step1"}
        step1_token = create_access_token(identity=email, additional_claims=temp_payload, expires_delta=timedelta(minutes=15))
        
        return True, f"Mã OTP đã được gửi đến {email}.", {"step1_token": step1_token}
    except Exception as e:
        return False, f"Lỗi hệ thống: {str(e)}", None
    finally:
        if conn: conn.close()


def verify_register_otp_step2(step1_token, input_otp):
    """BƯỚC 2: FE gửi step1_token + OTP lên -> Giải mã đối chiếu -> Trả về step2_token (Thẻ thông hành)"""
    try:
        try:
            decoded = decode_token(step1_token)
        except Exception:
            return False, "Phiên xác thực đã hết hạn (quá 15 phút). Vui lòng yêu cầu mã mới!", None
            
        if decoded.get("purpose") != "reg_step1":
            return False, "Mã thông báo không hợp lệ!", None

        saved_otp = decoded.get("otp")
        if str(saved_otp) != str(input_otp).strip():
            return False, "Mã OTP không chính xác!", None

        # Khớp OTP -> Cấp cho FE một thẻ thông hành (Valid trong 30 phút) để điền Form thông tin
        email = decoded.get("email")
        verified_payload = {"email": email, "purpose": "reg_step2"}
        step2_token = create_access_token(identity=email, additional_claims=verified_payload, expires_delta=timedelta(minutes=30))
        
        return True, "Xác thực Email thành công! Vui lòng điền thông tin cá nhân.", {"step2_token": step2_token}
    except Exception as e:
        return False, f"Lỗi xác thực: {str(e)}", None


def finalize_registration(step2_token, fullname, password, phone, address):
    """BƯỚC 3: FE nộp thông tin + step2_token -> Giải mã lấy Email -> Ghi đĩa DB"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        try:
            decoded = decode_token(step2_token)
        except Exception:
            return False, "Thời gian điền form quá lâu (hết 30 phút). Vui lòng đăng ký lại từ đầu!", None
            
        if decoded.get("purpose") != "reg_step2":
            return False, "Mã thông hành không hợp lệ!", None
            
        email = decoded.get("email")
        hashed_password = generate_password_hash(password)
        customer_role_uuid = _get_role_uuid(conn, 'Customer')
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check an toàn lần cuối
        cursor.execute("SELECT UserID FROM Users WHERE Email = %s;", (email,))
        if cursor.fetchone():
            return False, "Tài khoản với Email này đã tồn tại!", None

        sql_insert = """
            INSERT INTO Users (FullName, Email, PasswordHash, PhoneNumber, Address, RoleID, IsActive) 
            VALUES (%s, %s, %s, %s, %s, %s, TRUE) 
            RETURNING UserID::text AS userid, FullName AS fullname, Email AS email;
        """
        cursor.execute(sql_insert, (fullname, email, hashed_password, phone, address, customer_role_uuid))
        new_user = cursor.fetchone()
        conn.commit()
        
        return True, "🎉 Đăng ký tài khoản thành công!", dict(new_user)
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi lưu trữ tài khoản: {str(e)}", None
    finally:
        if conn: conn.close()


def login_user(email, password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối cơ sở dữ liệu", None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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
            return False, "Tài khoản chưa được kích hoạt hoặc đang bị khóa. Vui lòng liên hệ Admin!", None
            
        if not check_password_hash(user['passwordhash'], password):
            return False, "Mật khẩu không chính xác!", None

        user_payload = {
            "userid": user['userid'],
            "fullname": user['fullname'],
            "email": user['email'],
            "phone": user['phone'],
            "address": user['address'],
            "avatar": user['avatar'],
            "roleid": user['roleid'],
            "rolename": user['rolename'],
            "shop": None
        }

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

        access_token = create_access_token(
            identity=user['userid'],
            additional_claims={"roleid": user['roleid'], "rolename": user['rolename']}
        )

        return True, "Đăng nhập thành công!", {"access_token": access_token, "user": user_payload}
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi hệ thống: {str(e)}", None
    finally:
        if conn: conn.close()


# ================= HÀM ĐỔI MẬT KHẨU (ĐÃ ĐƯỢC KHÔI PHỤC BỌC THÉP) =================
def change_password(user_id, old_password, new_password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT PasswordHash FROM Users WHERE UserID = %s AND IsActive = TRUE;", (str(user_id),))
        user = cursor.fetchone()
        
        if not user: return False, "Người dùng không tồn tại hoặc tài khoản đang bị khóa", None
            
        saved_hash = user.get('passwordhash') or user.get('PasswordHash')
        if not check_password_hash(saved_hash, old_password):
            return False, "Mật khẩu hiện tại không đúng", None
            
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE Users SET PasswordHash = %s, UpdatedAt = CURRENT_TIMESTAMP WHERE UserID = %s;", (new_hash, str(user_id)))
        conn.commit()
        return True, "Cập nhật mật khẩu mới thành công", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()


def send_otp_email(receiver_email, otp, email_type="forgot"):
    """Bắn mail qua cổng REST API của Brevo. Dynamic giao diện Đăng ký / Quên mật khẩu cực đẹp."""
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

    title = "XÁC THỰC ĐĂNG KÝ" if email_type == "register" else "KHÔI PHỤC MẬT KHẨU"
    desc = "Chào mừng bạn đến với Sàn TMDT DUE. Vui lòng nhập mã xác thực OTP dưới đây để hoàn tất quy trình kích hoạt tài khoản đăng ký:" if email_type == "register" else "Hệ thống nhận được yêu cầu đặt lại mật khẩu truy cập. Vui lòng nhập mã xác thực bảo mật dưới đây:"

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; border: 1px solid #e2e8f0; border-radius: 20px; background-color: #ffffff; box-shadow: 0 10px 25px rgba(0,0,0,0.05);">
        <div style="text-align: center; margin-bottom: 25px;">
            <span style="font-size: 22px; font-weight: 900; color: #0f172a; letter-spacing: -0.5px;">TECH</span>
            <span style="font-size: 22px; font-weight: 900; color: #2563eb; letter-spacing: -0.5px;">TONIC</span>
            <p style="color: #64748b; font-size: 13px; margin-top: 5px; font-weight: 600;">{title} SÀN TMDT DUE</p>
        </div>
        
        <p style="color: #334155; font-size: 14px;">Xin chào,</p>
        <p style="color: #334155; font-size: 14px; line-height: 1.6;">{desc}</p>
        
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
        "sender": {"name": "Sàn TMDT DUE", "email": sender_mail},
        "to": [{"email": receiver_email}],
        "subject": f"[{otp}] Mã xác thực {title.lower()} sàn TMDT DUE",
        "htmlContent": html_content
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            if status_code in [200, 201, 202]:
                print(f"🎉 [BREVO DISPATCH SUCCESS]: Đã bắn OTP loại [{email_type}] tới -> {receiver_email}")
                return True
            return False
    except Exception as e:
        print(f"❌ [BREVO EXCEPTION]: {str(e)}")
        return False


def forgot_password(email):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        email = email.lower().strip()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID FROM Users WHERE Email = %s AND IsActive = TRUE;", (email,))
        if not cursor.fetchone():
            return False, "Email không tồn tại trong hệ thống hoặc chưa kích hoạt", None
            
        otp = str(random.randint(100000, 999999))
        expiry_time = datetime.now() + timedelta(minutes=15)
        
        cursor.execute("UPDATE Users SET ResetOTP = %s, OTPExpiry = %s WHERE Email = %s;", (otp, expiry_time, email))
        conn.commit()
        
        mail_sent = send_otp_email(email, otp, email_type="forgot")
        if mail_sent:
            return True, f"Mã khôi phục đã được gửi đến email {email}. Vui lòng kiểm tra hộp thư.", None
        else:
            cursor.execute("UPDATE Users SET ResetOTP = NULL, OTPExpiry = NULL WHERE Email = %s;", (email,))
            conn.commit()
            return False, "Hệ thống gửi email đang gặp rào cản mạng. Vui lòng thử lại sau.", None
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
        cursor.execute("SELECT ResetOTP, OTPExpiry FROM Users WHERE Email = %s AND IsActive = TRUE;", (email,))
        user = cursor.fetchone()
        if not user: return False, "Email không tồn tại hoặc tài khoản bị khóa", None
        
        saved_otp = user.get('resetotp') or user.get('ResetOTP')
        expiry = user.get('otpexpiry') or user.get('OTPExpiry')
        if not saved_otp or saved_otp != otp: return False, "Mã xác thực không hợp lệ", None
        if expiry < datetime.now(): return False, "Mã xác thực đã hết hạn", None
        return True, "Mã xác thực hợp lệ. Vui lòng đặt mật khẩu mới.", None
    except Exception as e: return False, f"Lỗi kiểm tra OTP: {str(e)}", None
    finally:
        if conn: conn.close()


def reset_password(email, otp, new_password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối Database", None
    try:
        email = email.lower().strip()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT ResetOTP, OTPExpiry FROM Users WHERE Email = %s AND IsActive = TRUE;", (email,))
        user = cursor.fetchone()
        if not user: return False, "Email không tồn tại", None
        
        saved_otp = user.get('resetotp') or user.get('ResetOTP')
        expiry = user.get('otpexpiry') or user.get('OTPExpiry')
        if saved_otp != otp: return False, "Mã OTP không hợp lệ", None
        if expiry < datetime.now():
            cursor.execute("UPDATE Users SET ResetOTP = NULL, OTPExpiry = NULL WHERE Email = %s;", (email,))
            conn.commit()
            return False, "Mã OTP đã hết hạn", None
            
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE Users SET PasswordHash = %s, ResetOTP = NULL, OTPExpiry = NULL, UpdatedAt = CURRENT_TIMESTAMP WHERE Email = %s;", (new_hash, email))
        conn.commit()
        return True, "Đổi mật khẩu thành công! Vui lòng đăng nhập lại.", None
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Lỗi đặt lại mật khẩu: {str(e)}", None
    finally:
        if conn: conn.close()