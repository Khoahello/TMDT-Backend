import psycopg2.extras
from data_manager import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime, timedelta
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_jwt_extended import create_access_token

def register_user(fullname, email, password, phone, address):
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Database", None

    try:
        # Ép email về chữ thường và xóa khoảng trắng thừa 2 đầu để chống lỗi tìm kiếm sau này
        email = email.lower().strip()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        hashed_password = generate_password_hash(password)
        
        sql_query = """
            INSERT INTO Users (FullName, Email, PasswordHash, PhoneNumber, Address, RoleID) 
            VALUES (%s, %s, %s, %s, %s, 3) 
            RETURNING UserID, FullName, Email, PhoneNumber, Address, RoleID;
        """
        cursor.execute(sql_query, (fullname, email, hashed_password, phone, address))
        new_user = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Đăng ký tài khoản thành công!", new_user
        
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        return False, "Email này đã được đăng ký", None
    except Exception as e:
        if conn: conn.rollback()
        print("Lỗi SQL Register:", str(e))
        return False, f"Lỗi cơ sở dữ liệu: {str(e)}", None

def login_user(email, password):
    conn = get_db_connection()
    if not conn:
        return False, "Lỗi kết nối Database", None

    try:
        email = email.lower().strip()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql_query = """
            SELECT u.UserID, u.FullName, u.Email, u.PasswordHash, u.RoleID, r.RoleName, u.IsActive
            FROM Users u
            JOIN Roles r ON u.RoleID = r.RoleID
            WHERE u.Email = %s;
        """
        cursor.execute(sql_query, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return False, "Email không tồn tại trong hệ thống", None

        saved_password_hash = user.get('passwordhash') or user.get('PasswordHash')
        is_active = user.get('isactive') if user.get('isactive') is not None else user.get('IsActive')

        if check_password_hash(saved_password_hash, password):
            if not is_active:
                return False, "Tài khoản của bạn đã bị khóa", None
            
            if 'passwordhash' in user: del user['passwordhash']
            if 'PasswordHash' in user: del user['PasswordHash']
            
            # --- BẮT ĐẦU TẠO JWT THẬT ---
            # Gói UserID và RoleID vào bên trong Token để sau này tái sử dụng
            identity_data = {
                "userid": str(user['userid']), # Ép chuỗi để không bị lỗi UUID
                "roleid": user['roleid']
            }
            # Tạo thẻ với thời hạn tùy chỉnh (mặc định của thư viện là 15 phút)
            access_token = create_access_token(
                identity=str(user['userid']), 
                additional_claims={"roleid": user['roleid']}
            )
            
            data = {"user": user, "access_token": access_token}
            return True, "Đăng nhập thành công", data
        else:
            return False, "Mật khẩu không chính xác", None
            
    except Exception as e:
        print("Lỗi SQL Login:", str(e))
        return False, "Lỗi trong quá trình kiểm tra đăng nhập", None
    
def change_password(user_id, old_password, new_password):
    """Nghiệp vụ đổi mật khẩu (Sử dụng UserID từ Token để bảo mật tuyệt đối)"""
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Tìm User theo mã ID bóc ra từ Token thay vì Email
        cursor.execute("SELECT PasswordHash FROM Users WHERE UserID = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return False, "Người dùng không tồn tại", None
            
        saved_hash = user.get('passwordhash') or user.get('PasswordHash')
        if not check_password_hash(saved_hash, old_password):
            return False, "Mật khẩu hiện tại không đúng", None
            
        new_hash = generate_password_hash(new_password)
        
        # Cập nhật bằng UserID
        cursor.execute("UPDATE Users SET PasswordHash = %s, UpdatedAt = CURRENT_TIMESTAMP WHERE UserID = %s", (new_hash, user_id))
        conn.commit()
        
        return True, "Cập nhật mật khẩu mới thành công", None
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("EMAIL_SENDER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    
    if not sender_email or not sender_password:
        print("⚠️ Chưa cấu hình EMAIL_SENDER hoặc EMAIL_PASSWORD trong file .env")
        return False

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = f"[{otp}] Mã xác thực khôi phục mật khẩu"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #1dbf73; text-align: center;">Xác Thực Tài Khoản</h2>
                <p>Chào bạn,</p>
                <p>Hệ thống nhận được yêu cầu khôi phục mật khẩu tài khoản của bạn. Vui lòng sử dụng mã OTP dưới đây để hoàn tất quá trình đặt lại mật khẩu:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #1dbf73; background: #f4f4f4; padding: 10px 20px; border-radius: 5px; border: 1px dashed #1dbf73;">
                        {otp}
                    </span>
                </div>
                <p style="color: #ff4d4f; font-size: 13px;">* Mã OTP này có hiệu lực trong vòng 15 phút. Tuyệt đối không chia sẻ mã này cho bất kỳ ai để tránh mất mát tài khoản.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #999; text-align: center;">Đây là email tự động từ hệ thống đồ án TMDT. Vui lòng không phản hồi email này.</p>
            </div>
        </body>
    </html>
    """
    message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi Email SMTP: {str(e)}")
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
            return True, f"Một mã OTP đã được gửi đến email {email}. Vui lòng kiểm tra hộp thư điện tử.", None
        else:
            return False, "Hệ thống không thể kết nối server gửi mail. Vui lòng kiểm tra cấu hình SMTP trong file .env.", None
            
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e), None
    finally:
        if conn: conn.close()

def verify_otp(email, otp):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None

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
        return False, str(e), None
    finally:
        if conn: conn.close()

def reset_password(email, otp, new_password):
    conn = get_db_connection()
    if not conn: return False, "Lỗi kết nối", None

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
        return False, str(e), None
    finally:
        if conn: conn.close()