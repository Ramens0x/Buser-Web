import os
import json
import time
import secrets
import requests
import jwt
import eventlet
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from flask_mail import Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from PIL import Image, ImageOps
from functools import wraps
from extensions import mail, db
from models import User, Order, Wallet, Bank, KYC
from price_service import price_service

# --- CÁC BIẾN CẤU HÌNH (Global Variables) ---
CONFIG_FILE = "config.json"
UPLOAD_FOLDER = 'uploads/bills'
KYC_UPLOAD_FOLDER = 'uploads/kyc'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

# Biến lưu trữ giá tạm thời
current_rates = {'bustabit': {'buy': 0, 'sell': 0}, 'usdt': {'buy': 0, 'sell': 0}}
app_settings = {}

# --- CÁC HÀM XỬ LÝ (HELPER FUNCTIONS) ---

def load_settings():
    """Tải cài đặt từ file config.json hoặc biến môi trường"""
    global app_settings
    if not os.path.exists(CONFIG_FILE):
        env_banks = os.environ.get('ADMIN_BANKS')
        default_banks = []
        if env_banks:
            try:
                default_banks = json.loads(env_banks) 
                print("✅ Đã tải thông tin Bank từ .env")
            except Exception as e:
                print(f"❌ Lỗi đọc ADMIN_BANKS từ .env: {e}")
                default_banks = []
        
        default_settings = {
            "admin_bustabit_id": "",
            "admin_usdt_wallet": "",
            "admin_ether_id": "",  
            "admin_sol_wallet": "",
            "admin_bnb_wallet": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "admin_banks": default_banks,
            "liquidity_usdt": 10000,
            "liquidity_btc": 1000000,
            "liquidity_eth": 1000000,
            "liquidity_bnb": 10,
            "liquidity_sol": 10,
            "coin_fees": {
                "bustabit": {"fee": 50000, "threshold": 20000},
                "ether": {"fee": 100000, "threshold": 50000},    
                "usdt": {"fee": 10000, "threshold": 1000},
                "sol": {"fee": 10000, "threshold": 10},
                "bnb": {"fee": 10000, "threshold": 5}
            },
            "supported_banks": [
                {"name": "Vietcombank (VCB)", "bin": "970436", "short_name": "Vietcombank"},
                {"name": "VietinBank (ICB)", "bin": "970415", "short_name": "VietinBank"},
                {"name": "Techcombank (TCB)", "bin": "970407", "short_name": "Techcombank"},
                {"name": "MBBank (MB)", "bin": "970422", "short_name": "MBBank"},
                {"name": "Á Châu (ACB)", "bin": "970416", "short_name": "ACB"},
                {"name": "BIDV", "bin": "970418", "short_name": "BIDV"},
                {"name": "Agribank", "bin": "970405", "short_name": "Agribank"},
                {"name": "Sacombank (STB)", "bin": "970403", "short_name": "Sacombank"},
                {"name": "VPBank", "bin": "970432", "short_name": "VPBank"},
                {"name": "TPBank", "bin": "970423", "short_name": "TPBank"},
                {"name": "HDBank", "bin": "970437", "short_name": "HDBank"}
            ],
            "fee_html_content": "",
            "maintenance_mode": "off"
        }
        save_settings(default_settings)
        app_settings = default_settings
        return default_settings

    try:
        with open(CONFIG_FILE, 'r') as f:
            app_settings = json.load(f)
    except json.JSONDecodeError: 
        return app_settings

    if os.environ.get('TELEGRAM_BOT_TOKEN'):
        app_settings['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN')
    if os.environ.get('TELEGRAM_CHAT_ID'):
        app_settings['TELEGRAM_CHAT_ID'] = os.environ.get('TELEGRAM_CHAT_ID')
        
    return app_settings

def save_settings(settings):
    global app_settings
    with open(CONFIG_FILE, 'w') as f: json.dump(settings, f, indent=4)
    app_settings = settings

def send_async_email(app, msg):
    """Gửi email bất đồng bộ (cần app context)"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✅ Đã gửi email tới {msg.recipients[0]}")
        except Exception as e:
            print(f"❌ Lỗi gửi email async: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_kyc_file(filename):
    ALLOWED = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def save_secure_image(file_storage, folder, prefix):
    """Lưu ảnh an toàn và nén ảnh"""
    try:
        img = Image.open(file_storage)
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')
        filename = f"{prefix}_{int(time.time())}.jpg"
        file_path = os.path.join(folder, secure_filename(filename))
        img.save(file_path, format='JPEG', quality=85, optimize=True)
        return filename
    except Exception as e:
        print(f"Lỗi xử lý ảnh: {e}")
        return None

def is_valid_image(file_stream):
    """Kiểm tra xem file có phải là ảnh thật không"""
    try:
        file_stream.seek(0, 2)
        size = file_stream.tell()
        file_stream.seek(0)
        img = Image.open(file_stream)
        width, height = img.size
        if width > 4000 or height > 4000: return False
        if size > 5 * 1024 * 1024: return False
        img.verify()
        if img.format not in ['JPEG', 'PNG', 'GIF']: return False
        file_stream.seek(0)
        return True
    except Exception:
        return False

def send_reset_email(user_email, reset_link):
    """Gửi email khôi phục mật khẩu"""
    try:
        # Lấy sender từ current_app config
        sender = current_app.config.get('MAIL_USERNAME')
        msg = Message('Đặt lại mật khẩu - Buser.ink',
                      sender=sender,
                      recipients=[user_email])
        msg.body = f'Xin chào,\n\nBạn đã yêu cầu đặt lại mật khẩu. Vui lòng click vào link sau:\n{reset_link}\n\nLink này sẽ hết hạn sau 15 phút.\n\nTrân trọng,\nBuser Team'
        
        # Vì hàm này thường gọi trong request context, ta có thể dùng mail.send trực tiếp 
        # hoặc spawn luồng async. Ở đây dùng current_app._get_current_object() để spawn.
        eventlet.spawn(send_async_email, current_app._get_current_object(), msg)
        print(f"✅ Đã queue email reset tới {user_email}")
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")

def get_user_from_request():
    """Lấy thông tin User từ Cookie Token"""
    token = request.cookies.get('access_token')
    if not token: return None
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        username = payload.get('username')
        if not username: return None
        return User.query.filter_by(username=username.lower()).first()
    except Exception:
        return None

def admin_required(f):
    """Decorator yêu cầu quyền Admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_user_from_request()
        if not user:
            return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401
        if user.role != 'Admin':
            return jsonify({"success": False, "message": "Bạn không có quyền truy cập (Admin only)"}), 403
        return f(*args, **kwargs)
    return decorated_function

def send_telegram_notification(message, order_id=None):
    """Gửi thông báo Telegram"""
    global app_settings
    
    # Ưu tiên lấy từ biến môi trường
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    # Nếu không có, lấy từ settings
    if not token: token = app_settings.get('TELEGRAM_BOT_TOKEN')
    if not chat_id: chat_id = app_settings.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        return # Chưa cấu hình thì bỏ qua
    
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    
    domain = os.environ.get('SITE_DOMAIN', 'http://127.0.0.1:5000')
    if order_id:
        payload['reply_markup'] = {
            'inline_keyboard': [[{'text': '✅ Xem chi tiết Dashboard', 'url': f'{domain}/admin_dashboard.html'}]]
        }
    try:
        requests.post(api_url, json=payload, timeout=3)
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

# --- CÁC HÀM CHẠY NGẦM (TASKS) ---

def clean_old_bills(app):
    """Xóa ảnh hóa đơn cũ > 90 ngày (Cần nhận tham số app để chạy trong Scheduler)"""
    with app.app_context():
        cutoff_date = datetime.now() - timedelta(days=90)
        old_orders = Order.query.filter(Order.created_at < cutoff_date).all()
        count = 0
        for order in old_orders:
            try:
                if order.payment_info:
                    info = json.loads(order.payment_info)
                    img_name = info.get('bill_image')
                    if img_name:
                        # Dùng app.config để lấy đường dẫn
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], img_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        info['bill_image'] = None
                        order.payment_info = json.dumps(info)
                        count += 1
            except Exception as e:
                print(f"Lỗi xóa bill đơn {order.id}: {e}")
        if count > 0:
            db.session.commit()
            print(f"🧹 Đã dọn dẹp {count} ảnh hóa đơn cũ.")

def cancel_expired_orders(app):
    """Hủy đơn hàng treo quá 15 phút"""
    with app.app_context():
        cutoff_time = datetime.now() - timedelta(minutes=15) # Sửa thành minutes=15
        expired = Order.query.filter(
            Order.status == 'pending',
            Order.created_at < cutoff_time
        ).all()
        count = 0
        for order in expired:
            order.status = 'cancelled'
            count += 1
        if count > 0:
            db.session.commit()
            print(f"⏰ Đã hủy {count} đơn hàng hết hạn.")

def update_price_task():
    """Cập nhật giá Coin"""
    global current_rates
    try:
        all_prices = price_service.get_all_prices()
        if all_prices:
            current_rates.update(all_prices)
    except Exception as e:
        print(f"⚠️ Lỗi cập nhật giá: {e}")

# --- HÀM KHỞI TẠO ADMIN (QUAN TRỌNG) ---
def create_system_admin():
    """Tự động tạo tài khoản Admin từ .env nếu chưa có"""
    env_admin_user = os.environ.get('ADMIN_USERNAME')
    env_admin_pass = os.environ.get('ADMIN_PASSWORD')

    if not env_admin_user or not env_admin_pass:
        print(">>> LƯU Ý: Chưa có ADMIN_USERNAME/PASSWORD trong .env (Bỏ qua tạo Admin tự động)")
        return

    admin_user = User.query.filter_by(username=env_admin_user).first()
    if not admin_user:
        hashed_pass = generate_password_hash(env_admin_pass)
        new_admin = User(
            username=env_admin_user,
            email=f"{env_admin_user}@system.local",
            password=hashed_pass,
            role="Admin",
            is_verified=True
        )
        db.session.add(new_admin)
        db.session.commit()
        print(f">>> 👑 Đã khởi tạo Admin mặc định: {env_admin_user}")
    else:
        # Nếu đã có user thì thôi, không làm gì cả
        pass