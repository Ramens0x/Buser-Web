import eventlet
eventlet.monkey_patch()
from flask import Flask, jsonify, request, send_file
from flask_wtf.csrf import CSRFProtect
from flask import render_template, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests 
import json
import os
from dotenv import load_dotenv
from price_service import price_service
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import random
import qrcode
from PIL import Image
import io
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
import jwt
from datetime import datetime, timedelta
from datetime import datetime, date
from flask_mail import Mail, Message
import time
from apscheduler.schedulers.background import BackgroundScheduler
from flask_migrate import Migrate
from utils import VietQR, generate_qr_code_image, remove_accents
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import or_
from functools import wraps
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

load_dotenv()

# --- [MỚI] CẤU HÌNH CSDL ---
app = Flask(__name__, static_folder='static', template_folder='templates')
# --- [START] CẤU HÌNH LOGGING NÂNG CAO ---
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = RotatingFileHandler('logs/buser.log', maxBytes=10240 * 1024, backupCount=10)
    
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Buser startup - Hệ thống đã khởi động')
UPLOAD_FOLDER = 'uploads/bills'
KYC_UPLOAD_FOLDER = 'uploads/kyc'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['KYC_UPLOAD_FOLDER'] = KYC_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # Giới hạn 15MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Tự tạo thư mục nếu chưa có
os.makedirs(KYC_UPLOAD_FOLDER, exist_ok=True)
csrf = CSRFProtect(app)

def send_async_email(app, msg):
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

def clean_old_bills():
    with app.app_context():
        # Chỉ tìm những đơn hàng cũ > 90 ngày
        cutoff_date = datetime.now() - timedelta(days=90)
        old_orders = Order.query.filter(Order.created_at < cutoff_date).all()
        
        count = 0
        for order in old_orders:
            try:
                if order.payment_info:
                    info = json.loads(order.payment_info)
                    img_name = info.get('bill_image')
                    if img_name:
                        # Xóa file vật lý
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], img_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        
                        # Cập nhật DB
                        info['bill_image'] = None
                        order.payment_info = json.dumps(info)
                        count += 1
            except Exception as e:
                print(f"Lỗi xóa bill đơn {order.id}: {e}")
        
        if count > 0:
            db.session.commit()
            print(f"🧹 Đã dọn dẹp {count} ảnh hóa đơn cũ.")

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # <-- Thay mật khẩu ứng dụng
mail = Mail(app)
# ☝️ KẾT THÚC KHỐI CẤU HÌNH
limiter = Limiter(
    get_remote_address,
    app=app
)
allowed_origins_env = os.environ.get('ALLOWED_ORIGINS')
if allowed_origins_env:
    ALLOWED_ORIGINS = allowed_origins_env.split(',')
else:
    # Mặc định cho phép cả production và localhost để dev dễ dàng
    ALLOWED_ORIGINS = ['https://Buser.ink', 'http://127.0.0.1:5500', 'http://localhost:5500']

CORS(app, supports_credentials=True, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
# Lấy địa chỉ Database từ biến môi trường
database_url = os.environ.get('DATABASE_URL', 'sqlite:///buser.db')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required!")
app.config['SECRET_KEY'] = SECRET_KEY
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, 
    cors_allowed_origins="*",
    async_mode='eventlet'
)

# --- Định nghĩa file ---
CONFIG_FILE = "config.json"


# --- ĐỊNH NGHĨA CÁC BẢNG CSDL (MODELS) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='User')
    reset_token = db.Column(db.String(100), nullable=True)
    reset_expiry = db.Column(db.DateTime, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    wallets = db.relationship('Wallet', backref='owner', lazy=True)
    banks = db.relationship('Bank', backref='owner', lazy=True)
    kyc = db.relationship('KYC', backref='user', uselist=False, lazy=True)
    __table_args__ = (
    db.Index('idx_user_email', 'email'),
    db.Index('idx_user_username', 'username'),)

class Wallet(db.Model):
    id = db.Column(db.String(10), primary_key=True, default=lambda: secrets.token_hex(4))
    coin_type = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    tag = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Bank(db.Model):
    id = db.Column(db.String(10), primary_key=True, default=lambda: secrets.token_hex(4))
    bank_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class KYC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    id_number = db.Column(db.String(20), nullable=False)  # Số CMND/CCCD
    id_front_image = db.Column(db.String(200), nullable=True)  # Ảnh mặt trước
    id_back_image = db.Column(db.String(200), nullable=True)   # Ảnh mặt sau
    selfie_image = db.Column(db.String(200), nullable=True)    # Ảnh selfie cầm CMND
    paper_image = db.Column(db.String(200), nullable=True)     # Ảnh giấy viết tay
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending/approved/rejected
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)
    __table_args__ = (
    db.Index('idx_kyc_user_id', 'user_id'),
    db.Index('idx_kyc_status', 'status'),)

class Order(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    mode = db.Column(db.String(10), nullable=False)
    coin = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)
    amount_vnd = db.Column(db.Float, nullable=False)
    amount_coin = db.Column(db.Float, nullable=False)
    payment_info = db.Column(db.Text, nullable=True) 
    user_wallet_id = db.Column(db.String(10), nullable=True)
    user_bank_id = db.Column(db.String(10), nullable=True)
    __table_args__ = (
        db.Index('idx_status', 'status'),
        db.Index('idx_username', 'username'),
        db.Index('idx_created_at', 'created_at'),
    )

# --- Biến tạm ---
current_rates = {'bustabit': {'buy': 0, 'sell': 0}, 'usdt': {'buy': 0, 'sell': 0}}
app_settings = {}

# --- HÀM QUẢN LÝ CÀI ĐẶT ---
def load_settings():
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
        else:
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
                "bustabit": {"fee": 50000, "threshold": 20000},  # Phí 50k, miễn phí nếu > 20k
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
            "fee_html_content": """
                <tr>
                    <td class="text-center">Bits (BTC)</td>
                    <td class="text-center">MUA</td>
                    <td><span style="color:red">50.000đ</span> (< 20k Bits) | <span style="color:green">FREE</span> (> 20k Bits)</td>
                </tr>
                <tr>
                    <td class="text-center">USDT</td>
                    <td class="text-center">MUA/BÁN</td>
                    <td style="color:green">MIỄN PHÍ</td>
                </tr>
            """,
            "maintenance_mode": "off"
        }
        save_settings(default_settings)
        app_settings = default_settings
        return default_settings
    try:
        with open(CONFIG_FILE, 'r') as f:
            app_settings = json.load(f)
    except json.JSONDecodeError: return app_settings

    if os.environ.get('TELEGRAM_BOT_TOKEN'):
        app_settings['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN')
    if os.environ.get('TELEGRAM_CHAT_ID'):
        app_settings['TELEGRAM_CHAT_ID'] = os.environ.get('TELEGRAM_CHAT_ID')
        
    return app_settings


def save_settings(settings):
    global app_settings
    with open(CONFIG_FILE, 'w') as f: json.dump(settings, f, indent=4)
    app_settings = settings

def send_reset_email(user_email, reset_link):
    try:
        msg = Message('Đặt lại mật khẩu - Buser.ink',
                      sender=app.config.get('MAIL_USERNAME'),
                      recipients=[user_email])
        msg.body = f'Xin chào,\n\nBạn đã yêu cầu đặt lại mật khẩu. Vui lòng click vào link sau:\n{reset_link}\n\nLink này sẽ hết hạn sau 15 phút.\n\nTrân trọng,\nBuser Team'
        mail.send(msg)
        print(f"✅ Đã gửi email reset tới {user_email}")
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")

# --- HÀM LẤY USER TỪ TOKEN ---
def get_user_from_request():
    token = request.cookies.get('access_token')
    
    if not token:
        return None

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        username = payload.get('username')
        if not username:
            return None
        return User.query.filter_by(username=username.lower()).first()
    except Exception:
        return None

# --- DECORATOR KIỂM TRA QUYỀN ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_user_from_request()
        if not user:
            return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401
        if user.role != 'Admin':
            return jsonify({"success": False, "message": "Bạn không có quyền truy cập (Admin only)"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route("/api/config/supported-banks", methods=['GET'])
def get_supported_banks():
    settings = load_settings()
    return jsonify({"success": True, "banks": settings.get('supported_banks', [])})

# --- API GIÁ & TÍNH TOÁN ---
@app.route("/api/prices")
def api_get_prices(): 
    return jsonify(current_rates)

@app.route("/api/calculate", methods=['POST'])
def api_calculate_swap():
    data = request.json
    amount_in = float(data.get('amount', 0))
    direction = data.get('direction', 'from') 
    mode = data.get('mode', 'sell')
    coin_type = data.get('coin', 'bustabit') 
    
    settings = load_settings()
    coin_fees = settings.get('coin_fees', {})
    fee_data = coin_fees.get(coin_type, {})

    if isinstance(fee_data, (int, float)):
        base_fee = float(fee_data)
        threshold = 0.0
    else:
        base_fee = float(fee_data.get('fee', 0))
        threshold = float(fee_data.get('threshold', 0))
    
    if current_rates.get(coin_type, {}).get('buy', 0) == 0:
        from price_service import price_service
        all_prices = price_service.get_all_prices()
        if all_prices:
            current_rates.update(all_prices)
        
    amount_out = 0.0
    current_fee = base_fee 

    try:
        if mode == 'buy':
            rate = float(current_rates.get(coin_type, {}).get('buy', 0))
            if rate > 0:
                if threshold > 0:
                    amount_in_coin = amount_in
                    if direction == 'from': 
                        amount_in_coin = amount_in / rate
                    
                    if amount_in_coin >= threshold:
                        current_fee = 0.0

                if direction == 'from': 
                    net_vnd = amount_in - current_fee
                    if net_vnd < 0: net_vnd = 0.0
                    amount_out = net_vnd / rate
                else: 
                    amount_out = (amount_in * rate) + current_fee

        elif mode == 'sell':
            rate = float(current_rates.get(coin_type, {}).get('sell', 0))
            if rate > 0:
                if direction == 'from':
                    amount_out = amount_in * rate
                else:
                    amount_out = amount_in / rate
                
        return jsonify({
            'amount_out': amount_out,
            'fee_applied': current_fee,     
            'threshold_info': threshold     
        })

    except Exception as e:
        print(f"Calc Error: {e}")
        return jsonify({"amount_out": 0}), 200

# --- API USER ---
@app.route("/api/register", methods=['POST'])
@limiter.limit("3 per hour")
def api_register_user():
    data = request.json
    username_raw, email, password = data.get('username'), data.get('email'), data.get('password')
    if not all([username_raw, email, password]): 
        return jsonify({"success": False, "message": "Vui lòng nhập đủ thông tin"}), 400
    
    username = username_raw.lower().strip()

    forbidden_keywords = [
        'admin', 'root', 'system', 'buser', 'support', 'manager', 
        'mod', 'moderator', 'help', 'info', 'contact', 'superuser', 
        'administrator', 'staff', 'bqt', 'quantri', 'cskh', 'hotro',
        'bot', 'billing', 'security', 'owner'
    ]

    for word in forbidden_keywords:
        if word in username:
            return jsonify({
                "success": False, 
                "message": f"Tên đăng nhập không được chứa từ khóa hệ thống: '{word}'"
            }), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "message": "Tên đăng nhập đã tồn tại"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email đã được sử dụng"}), 400
    
    hashed_password = generate_password_hash(password)
    
    # Tạo token xác thực
    verify_token = secrets.token_hex(20)
    
    # Lưu user với trạng thái chưa xác thực
    new_user = User(
        username=username, 
        email=email, 
        password=hashed_password, 
        role="User",
        is_verified=False,              
        verification_token=verify_token 
    )
    db.session.add(new_user)
    db.session.commit()
    
    try:
        domain = os.environ.get('SITE_DOMAIN', request.host_url.rstrip('/'))
        link = f"{domain}/api/verify-email/{verify_token}" 
        
        msg = Message('Xác thực tài khoản - Buser.ink',
                      sender=app.config.get('MAIL_USERNAME'),
                      recipients=[email])
        msg.body = f"Chào {username},\n\nVui lòng click vào link sau để kích hoạt tài khoản:\n{link}\n\nCảm ơn!"
        
        eventlet.spawn(send_async_email, app, msg)
        
    except Exception as e:
        print(f"Lỗi setup gửi mail: {e}")
    
    return jsonify({"success": True, "message": "Đăng ký thành công! Vui lòng kiểm tra Email để kích hoạt tài khoản."})

# [ API VERIFY EMAIL]
@app.route("/api/verify-email/<token>", methods=['GET'])
def verify_email_token(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return "<h3>Lỗi: Link xác thực không hợp lệ hoặc đã hết hạn!</h3>", 400
    
    if user.is_verified:
        return "<h3>Tài khoản đã được xác thực trước đó. <a href='/login.html'>Đăng nhập ngay</a></h3>"
        
    user.is_verified = True
    user.verification_token = None # Xóa token sau khi dùng
    db.session.commit()
    
    return "<h3>✅ Xác thực thành công! Bạn có thể <a href='/login.html'>Đăng nhập ngay</a></h3>"

@app.route("/api/login", methods=['POST'])
@limiter.limit("10 per 15 minute")
def api_login_user():
    data = request.json
    username_raw, password = data.get('username'), data.get('password')
    if not all([username_raw, password]): 
        return jsonify({"success": False, "message": "Vui lòng nhập đủ thông tin"}), 400
    username = username_raw.lower()
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "Tên đăng nhập không tồn tại"}), 404
    if not user.is_verified:
        return jsonify({"success": False, "message": "Tài khoản chưa kích hoạt. Vui lòng kiểm tra Email!"}), 403

    if check_password_hash(user.password, password):
        # Tạo payload
        payload = {
            'username': user.username,
            'exp': datetime.now() + timedelta(hours=2) 
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

        # Tạo response
        response = jsonify({
            "success": True, 
            "message": "Đăng nhập thành công!",
            "user": {"username": user.username, "email": user.email, "role": user.role}
            # KHÔNG trả về token ở đây nữa để tránh lộ
        })
        
        # [QUAN TRỌNG] Set HttpOnly Cookie
        response.set_cookie(
            'access_token', 
            token, 
            httponly=True,  # JS không đọc được
            secure=True,   # Đặt True nếu chạy HTTPS (Production), False nếu chạy Localhost
            samesite='Strict', # Chống CSRF cơ bản
            max_age=2*60*60
        )
        return response
    else:
        return jsonify({"success": False, "message": "Sai mật khẩu"}), 401

@app.route("/api/logout", methods=['POST'])
def api_logout():
    response = jsonify({"success": True, "message": "Đăng xuất thành công"})
    response.set_cookie('access_token', '', expires=0) # Xóa cookie
    return response

@app.route("/api/change-password", methods=['POST'])
def api_change_password():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    old_pass, new_pass = data.get('old_password'), data.get('new_password')
    if not check_password_hash(user.password, old_pass): 
        return jsonify({"success": False, "message": "Mật khẩu cũ không chính xác"}), 400
    
    user.password = generate_password_hash(new_pass)
    db.session.commit()
    return jsonify({"success": True, "message": "Đổi mật khẩu thành công!"})

@app.route("/api/change-email", methods=['POST'])
def api_change_email():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    new_email = data.get('new_email')
    if not new_email: return jsonify({"success": False, "message": "Email không được để trống"}), 400
    
    if User.query.filter_by(email=new_email).first():
        return jsonify({"success": False, "message": "Email này đã được sử dụng"}), 400
        
    user.email = new_email
    db.session.commit()
    return jsonify({"success": True, "message": "Cập nhật email thành công!"})

@app.route("/api/forgot-password", methods=['POST'])
@limiter.limit("5 per minute")
def api_forgot_password():
    data = request.json
    email = data.get('email')
    if not email: return jsonify({"success": False, "message": "Vui lòng nhập email"}), 400
    
    user = User.query.filter_by(email=email).first()
    if user:
        token = secrets.token_hex(20)
        expiry_time = datetime.now() + timedelta(minutes=15)
        user.reset_token = token
        user.reset_expiry = expiry_time
        db.session.commit()
        
        # Cách 1: Tự động lấy domain hiện tại
        domain = request.host_url.rstrip('/')
        reset_link = f"{domain}/reset-password.html?token={token}"
        send_reset_email(email, reset_link)
        
    return jsonify({"success": True, "message": "Nếu email tồn tại, vui lòng kiểm tra hộp thư (kể cả mục Spam)."})

@app.route("/api/reset-password", methods=['POST'])
@limiter.limit("5 per minute")
def api_reset_password():
    data = request.json
    token, new_password = data.get('token'), data.get('new_password')
    if not token or not new_password: 
        return jsonify({"success": False, "message": "Thiếu thông tin"}), 400
    
    user = User.query.filter_by(reset_token=token).first()
    if not user: 
        return jsonify({"success": False, "message": "Token không hợp lệ"}), 400
    
    if datetime.now() > user.reset_expiry:
        user.reset_token = None
        user.reset_expiry = None
        db.session.commit()
        return jsonify({"success": False, "message": "Token đã hết hạn"}), 400
        
    user.password = generate_password_hash(new_password)
    user.reset_token = None
    user.reset_expiry = None
    db.session.commit()
    return jsonify({"success": True, "message": "Đặt lại mật khẩu thành công!"})

@app.route("/api/send-contact", methods=['POST'])
@limiter.limit("5 per hour") # Chống spam: Chỉ cho gửi 5 mail/giờ/IP
def send_contact_email():
    data = request.json
    name = data.get('name')
    user_email = data.get('email')
    subject = data.get('subject')
    message_content = data.get('message')
    
    if not all([name, user_email, subject, message_content]):
        return jsonify({"success": False, "message": "Vui lòng điền đầy đủ thông tin"}), 400
        
    try:
        # Gửi email đến cho Admin (Chính là email cấu hình trong .env)
        admin_email = app.config['MAIL_USERNAME']
        
        msg = Message(
            subject=f"[LIÊN HỆ BUSER] {subject}",
            sender=admin_email,
            recipients=[admin_email], # Gửi cho chính mình
            reply_to=user_email # Để khi bấm Reply sẽ trả lời cho khách
        )
        
        msg.body = f"""
        📩 CÓ TIN NHẮN LIÊN HỆ MỚI TỪ WEBSITE:
        
        - Họ tên: {name}
        - Email khách: {user_email}
        - Tiêu đề: {subject}
        
        --------------------------------
        NỘI DUNG:
        {message_content}
        --------------------------------
        """
        
        mail.send(msg)
        return jsonify({"success": True, "message": "Đã gửi liên hệ thành công"})
        
    except Exception as e:
        print(f"Lỗi gửi mail liên hệ: {e}")
        return jsonify({"success": False, "message": "Lỗi server, vui lòng thử lại sau"}), 500

# --- API TẠO ĐƠN HÀNG (DÙNG CSDL) ---
@app.route("/api/create-order", methods=['POST'])
@limiter.limit("5 per minute")
def create_order():
    
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Dữ liệu không hợp lệ"}), 400
    
    mode = data.get('mode')
    coin_type = data.get('coin', '').lower()

    if coin_type not in ALLOWED_COINS:
        return jsonify({"success": False, "message": "Loại coin không hợp lệ"}), 400
        
    
    amount_from, amount_to = float(data.get('amount_from', 0)), float(data.get('amount_to', 0))
    wallet_id, bank_id = data.get('wallet_id'), data.get('bank_id')

    # Xác định số tiền VNĐ
    transaction_vnd = amount_from if mode == 'buy' else amount_to
    KYC_LIMIT = 100000000
    if transaction_vnd > KYC_LIMIT:
        kyc_record = KYC.query.filter_by(user_id=user.id).first()
        if not kyc_record or kyc_record.status != 'approved':
            return jsonify({
                "success": False, 
                "message": f"Giao dịch từ {KYC_LIMIT:,.0f} VNĐ trở lên yêu cầu tài khoản phải xác minh danh tính (KYC) thành công!"
            }), 403
    
    if mode == 'buy':
        settings = load_settings()
        limit = 0
        if coin_type in ['bustabit', 'btc']: limit = float(settings.get('liquidity_btc', 0))
        elif coin_type == 'usdt': limit = float(settings.get('liquidity_usdt', 0))
        elif coin_type in ['ether', 'eth']: limit = float(settings.get('liquidity_eth', 0))
        elif coin_type == 'bnb': limit = float(settings.get('liquidity_bnb', 0))
        elif coin_type == 'sol': limit = float(settings.get('liquidity_sol', 0))
        else: limit = 1000000 
        
        if amount_to > limit:
            return jsonify({"success": False, "message": f"Số lượng mua vượt quá thanh khoản hiện có ({limit:,.4f} {coin_type.upper()})."}), 400

    def get_unique_order_id():
        while True:
            digits = ''.join([str(random.randint(0, 9)) for _ in range(8)])
            oid = f"T{digits}"
            if not Order.query.filter_by(id=oid).first(): return oid

    transaction_id = get_unique_order_id() 
    
    # --- Lấy tên người dùng cho nội dung CK (Mua) ---
    user_account_name = ""
    kyc_info = KYC.query.filter_by(user_id=user.id).first()
    
    # 1. Ưu tiên KYC
    if kyc_info and kyc_info.full_name:
        user_account_name = remove_accents(kyc_info.full_name)
    else:
        # 2. Lấy từ Tên Ví
        if wallet_id:
            selected_wallet = Wallet.query.filter_by(id=wallet_id).first()
            if selected_wallet and selected_wallet.name:
                user_account_name = remove_accents(selected_wallet.name)
        
        # 3. Lấy từ Tên trong NGÂN HÀNG (Dùng cho đơn BÁN)
        if not user_account_name and bank_id:
            selected_bank = Bank.query.filter_by(id=bank_id).first()
            if selected_bank and selected_bank.account_name:
                user_account_name = remove_accents(selected_bank.account_name)

        # 4. Chặn nếu vẫn thiếu tên
        if not user_account_name:
            return jsonify({
                "success": False, 
                "message": "Vui lòng cập nhật Họ và Tên chính xác trong Ví hoặc Ngân hàng để tạo đơn."
            }), 400
            
    transfer_keywords = ["ck tien", "chuyen tien", "hoan tien", "chuyen khoan", "gui tien", "thanh toan", "tra tien hang"]
    
    random_suffix = random.choice(transfer_keywords)

    full_transfer_content = f"{transaction_id} {user_account_name} {random_suffix}"
    
    # Lấy tên chủ TK Admin từ settings (nếu có) hoặc fix cứng
    settings = load_settings()
    admin_banks = settings.get('admin_banks', [])
    admin_name_fixed = "HOANG NGOC SON" 
    if admin_banks and len(admin_banks) > 0:
        # Lấy tên của bank đầu tiên trong list admin
        admin_name_fixed = remove_accents(admin_banks[0].get('name', 'HOANG NGOC SON'))
        
    sell_transfer_content = f"{transaction_id} {admin_name_fixed} transfer"
    # ------------------------------------------------------

    payment_info_dict = {}

    if mode == 'buy':
        admin_banks_list = settings.get('admin_banks', [])
        if not admin_banks_list:
            return jsonify({"success": False, "message": "Lỗi hệ thống: Admin chưa cấu hình tài khoản nhận tiền."}), 500
            
        selected_bank = random.choice(admin_banks_list)
        admin_bin = selected_bank.get('bin')
        admin_account = selected_bank.get('acc')
        admin_name = selected_bank.get('name')
        bank_label = selected_bank.get('bank_name', 'Ngân hàng')

        viet_qr = VietQR(); viet_qr.set_beneficiary_organization(admin_bin, admin_account); viet_qr.set_transaction_amount(str(int(amount_from))); viet_qr.set_additional_data_field_template(full_transfer_content);
        qr_data_string = viet_qr.build()
        payment_info_dict = {
            "bin": admin_bin, "bank_name": bank_label, "bank": f"{bank_label} (BIN: {admin_bin})",
            "account_number": admin_account, "account_name": admin_name, 
            "amount": int(amount_from), "content": full_transfer_content, "qr_data_string": qr_data_string
        }
    else: 
        if coin_type == 'bustabit': wallet_address = settings.get('admin_bustabit_id'); network = "Bustabit"
        elif coin_type == 'ether': wallet_address = settings.get('admin_ether_id'); network = "Ether"
        elif coin_type == 'sol': wallet_address = settings.get('admin_sol_wallet'); network = "Solana"
        elif coin_type == 'bnb': wallet_address = settings.get('admin_bnb_wallet'); network = "BEP-20 (BSC)"
        else: wallet_address = settings.get('admin_usdt_wallet'); network = "BEP-20 (BSC)"

        payment_info_dict = {
            "memo": "", "wallet_address": wallet_address, "network": network,
            "content": full_transfer_content,
            "sell_content": sell_transfer_content # <--- Gửi nội dung CK Bán xuống DB
        }
    
    new_order = Order(
        id=transaction_id, username=user.username, mode=mode, coin=coin_type,
        amount_vnd = amount_from if mode == 'buy' else amount_to,
        amount_coin = amount_to if mode == 'buy' else amount_from,
        user_wallet_id = wallet_id, user_bank_id = bank_id,
        payment_info = json.dumps(payment_info_dict)
    )
    db.session.add(new_order)
    db.session.commit()

    socketio.emit('admin_new_order', {'order_id': new_order.id})

    # Gửi Telegram
    try:
        if new_order.mode == 'buy':
            message = f"🔔 *Đơn MUA Mới*\nMã: *{new_order.id}*\nUser: *{new_order.username}*\nVNĐ: *{new_order.amount_vnd:,.0f}*\nND: `{full_transfer_content}`"
        else:
            message = f"🔔 *Đơn BÁN Mới*\nMã: *{new_order.id}*\nUser: *{new_order.username}*\nCoin: *{new_order.amount_coin:.8f}*\nVNĐ: *{new_order.amount_vnd:,.0f}*\nND Admin CK: `{sell_transfer_content}`"
        eventlet.spawn(send_telegram_notification, message, order_id=new_order.id)
    except Exception as e: print(f"Lỗi Telegram: {e}")

    return jsonify({"success": True, "order": {
        "id": new_order.id, "username": new_order.username, "mode": new_order.mode,
        "coin": new_order.coin, "status": new_order.status, "created_at": new_order.created_at.isoformat(),
        "amount_vnd": new_order.amount_vnd, "amount_coin": new_order.amount_coin,
        "payment_info": payment_info_dict
    }})

# --- API UPLOAD BILL & XEM BILL ---
@app.route("/api/upload-bill", methods=['POST'])
def upload_bill():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    if 'bill_image' not in request.files: return jsonify({"success": False, "message": "Không có file"}), 400
    
    file = request.files['bill_image']
    order_id = request.form.get('order_id')
    if not is_valid_image(file):
        return jsonify({"success": False, "message": "File không hợp lệ hoặc bị lỗi!"}), 400
    
    if file and allowed_file(file.filename):
        prefix = f"{order_id}_{user.username}"
        filename = save_secure_image(file, app.config['UPLOAD_FOLDER'], prefix)
        
        if not filename:
            return jsonify({"success": False, "message": "Lỗi khi xử lý ảnh. Vui lòng thử lại."}), 500
        
        order = Order.query.filter_by(id=order_id, username=user.username).first()
        if order:
            payment_info = json.loads(order.payment_info or '{}')
            payment_info['bill_image'] = filename
            order.payment_info = json.dumps(payment_info)
            db.session.commit()
            
            # Báo Telegram cho Admin
            try:
                msg = f"📸 *BILL MỚI* \nUser: {user.username}\nĐơn: {order_id}"
                send_telegram_notification(msg, order_id=order.id)
            except: pass

            return jsonify({"success": True, "filename": filename, "message": "Đã tải ảnh lên thành công!"})
    return jsonify({"success": False, "message": "File không hợp lệ"}), 400

@app.route("/api/admin/bill/<path:filename>")
@admin_required
def get_bill_image(filename):
    user = get_user_from_request()
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# --- [MỚI] API LẤY CHI TIẾT ĐƠN HÀNG (CHO TRANG THANH TOÁN) ---
@app.route("/api/order/<order_id>", methods=['GET'])
def get_order_detail(order_id):
    # Cho phép cả User (để xem đơn của mình) và Admin (để xem đơn khách)
    user = get_user_from_request()
    if not user:
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401

    order = Order.query.filter_by(id=order_id).first()
    if not order:
        return jsonify({"success": False, "message": "Không tìm thấy đơn hàng"}), 404

    # Bảo mật: Nếu không phải Admin, User chỉ được xem đơn của chính mình
    if user.role != 'Admin' and order.username != user.username:
        return jsonify({"success": False, "message": "Bạn không có quyền xem đơn này"}), 403

    # Trả về dữ liệu y hệt như lúc tạo đơn
    payment_info = json.loads(order.payment_info) if order.payment_info else {}
    
    qr_data_string = payment_info.get('qr_data_string', "")
    if order.mode == 'buy' and not qr_data_string:
        admin_bin = payment_info.get('bin') # Lấy BIN từ đơn hàng
        admin_account = payment_info.get('account_number')
        
        if admin_bin and admin_account:
            try:
                viet_qr = VietQR()
                viet_qr.set_beneficiary_organization(admin_bin, admin_account)
                viet_qr.set_transaction_amount(str(int(order.amount_vnd)))
                viet_qr.set_additional_data_field_template(order.id)
                qr_data_string = viet_qr.build()
            except Exception as e:
                print(f"Error rebuilding QR: {e}")

    return jsonify({
        "success": True,
        "order": {
            "id": order.id,
            "username": order.username,
            "mode": order.mode,
            "coin": order.coin,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin,
            "user_wallet_id": order.user_wallet_id,
            "user_bank_id": order.user_bank_id,
            "payment_info": payment_info,
            "qr_data_string": qr_data_string 
        }
    })

# --- API ADMIN ---
@app.route("/api/admin/settings", methods=['GET', 'POST'])
@admin_required
def admin_settings():
    user = get_user_from_request()
    if request.method == 'GET':
        return jsonify({"success": True, "settings": load_settings()})
    if request.method == 'POST':
        save_settings(request.json)
        try:
            msg = f"⚠️ *CẢNH BÁO BẢO MẬT*\nAdmin vừa cập nhật CÀI ĐẶT HỆ THỐNG (Bank, Wallet, Phí...).\nVui lòng kiểm tra nếu không phải bạn làm."
            send_telegram_notification(msg)
        except: pass

        return jsonify({"success": True, "message": "Cài đặt đã được lưu!"})

@app.route("/api/generate-qr")
def get_qr_image():
    data = request.args.get('data', '');
    if not data: return "Missing data", 400
    img = generate_qr_code_image(data); img_io = io.BytesIO(); img.save(img_io, 'PNG'); img_io.seek(0);
    return send_file(img_io, mimetype='image/png')

# --- [MỚI] HÀM GỬI THÔNG BÁO TELEGRAM (NÂNG CẤP) ---
def send_telegram_notification(message, order_id=None):

    global app_settings

    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not token:
        token = app_settings.get('TELEGRAM_BOT_TOKEN')
    if not chat_id:
        chat_id = app_settings.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id or str(token).strip() == "" or str(chat_id).strip() == "":
        print(">>> LƯU Ý: Chưa cấu hình Telegram Bot. Bỏ qua thông báo.")
        return
    
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
        }
    
    domain = os.environ.get('SITE_DOMAIN', 'http://127.0.0.1:5000')

    if order_id:
        payload['reply_markup'] = {
            'inline_keyboard': [[
                {
                    'text': '✅ Xem chi tiết Dashboard',
                    
                    'url': f'{domain}/admin_dashboard.html'
                }
            ]]
         }
        try:
            response = requests.post(api_url, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"✅ Đã gửi Telegram: {message[:50]}...")
            else:
                print(f"⚠️ Telegram lỗi: {response.text}")
        except Exception as e:
            print(f"❌ Lỗi khi gửi thông báo Telegram: {e}")

# --- API VÍ/NGÂN HÀNG CỦA USER ---
@app.route("/api/user/wallets", methods=['GET'])
def get_user_wallets():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    coin_type = request.args.get('coin_type', 'bustabit')
    wallets = Wallet.query.filter_by(user_id=user.id, coin_type=coin_type).all()
    wallets_list = [{"id": w.id, "coin_type": w.coin_type, "address": w.address, "tag": w.tag, "name": w.name, "phone": w.phone} for w in wallets]
    return jsonify({"success": True, "wallets": wallets_list})

ALLOWED_COINS = ['bustabit', 'ether', 'usdt', 'bnb', 'sol', 'btc', 'eth']

@app.route("/api/user/add-wallet", methods=['POST'])
def add_user_wallet():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    coin_type = data.get('coin_type')
    if coin_type not in ALLOWED_COINS:
        return jsonify({"success": False, "message": "Loại coin không hợp lệ"}), 400

    new_wallet = Wallet(
        coin_type=data.get('coin_type'), address=data.get('address'),
        tag=data.get('tag'), name=data.get('name'), phone=data.get('phone'),
        user_id=user.id
    )
    db.session.add(new_wallet)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã thêm ví thành công!"})

@app.route("/api/user/delete-wallet", methods=['POST'])
def delete_user_wallet():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    wallet_id = data.get('wallet_id')
    # Tìm ví dựa trên ID VÀ ID của user (để đảm bảo user chỉ xóa ví của chính họ)
    wallet_to_delete = Wallet.query.filter_by(id=wallet_id, user_id=user.id).first()
    if not wallet_to_delete:
        return jsonify({"success": False, "message": "Không tìm thấy ví hoặc bạn không có quyền xóa"}), 404
    db.session.delete(wallet_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã xóa ví thành công!"})

@app.route("/api/user/banks", methods=['GET'])
def get_user_banks():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    banks = Bank.query.filter_by(user_id=user.id).all()
    banks_list = [{"id": b.id, "bank_name": b.bank_name, "account_number": b.account_number, "account_name": b.account_name} for b in banks]
    return jsonify({"success": True, "banks": banks_list})

@app.route("/api/user/add-bank", methods=['POST'])
def add_user_bank():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    account_number = data.get('account_number', '').strip()
    account_name = data.get('account_name', '').strip().upper()

    if not account_number.isdigit():
        return jsonify({"success": False, "message": "Số tài khoản chỉ được chứa chữ số"}), 400
    
    if len(account_number) < 6 or len(account_number) > 20:
        return jsonify({"success": False, "message": "Số tài khoản không hợp lệ (6-20 ký tự)"}), 400
    
    if not account_name or len(account_name) < 3:
        return jsonify({"success": False, "message": "Tên chủ tài khoản không hợp lệ"}), 400
    

    new_bank = Bank(
        bank_name=data.get('bank_name'),
        account_number=data.get('account_number'),
        account_name=data.get('account_name'),
        user_id=user.id
    )
    db.session.add(new_bank)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã thêm ngân hàng thành công!"})

@app.route("/api/user/delete-bank", methods=['POST'])
def delete_user_bank():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    data = request.json
    bank_id = data.get('bank_id')
    # Tìm bank dựa trên ID VÀ ID của user
    bank_to_delete = Bank.query.filter_by(id=bank_id, user_id=user.id).first()
    if not bank_to_delete:
        return jsonify({"success": False, "message": "Không tìm thấy ngân hàng hoặc bạn không có quyền xóa"}), 404
    
    db.session.delete(bank_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã xóa ngân hàng thành công!"})

@app.route("/api/user/cancel-order", methods=['POST'])
def user_cancel_order():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    data = request.json
    order_id = data.get('order_id')
    order = Order.query.filter_by(id=order_id, username=user.username, status='pending').first()
    if not order:
        return jsonify({"success": False, "message": "Không tìm thấy đơn hàng hoặc đơn hàng đã được xử lý"}), 404
    order.status = 'cancelled'
    db.session.commit()
    return jsonify({"success": True, "message": "Đã hủy đơn hàng thành công!"})

@app.route("/api/admin/cancel-order", methods=['POST'])
@admin_required
def admin_cancel_order():
    user = get_user_from_request()
    data = request.json
    order_id = data.get('order_id')
    order = Order.query.filter_by(id=order_id, status='pending').first()
    if not order:
        return jsonify({"success": False, "message": "Không tìm thấy đơn hàng hoặc đơn hàng đã được xử lý"}), 404
    order.status = 'cancelled'
    db.session.commit()

    try:
        message = (
            f"⛔ *ADMIN HỦY ĐƠN*\n"
            f"Mã GD: *{order.id}*\n"
            f"User: *{order.username}*"
            )
        send_telegram_notification(message)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

    socketio.emit('order_completed', {'order_id': order.id}, room=order.id)
    return jsonify({"success": True, "message": f"Admin đã hủy đơn hàng {order_id}"})

    # --- API ADMIN ĐỂ XEM VÀ DUYỆT GIAO DỊCH ---
@app.route("/api/admin/transactions", methods=['GET'])
@admin_required
def get_admin_transactions():
    user = get_user_from_request()

    # 1. Lấy danh sách đơn hàng đang chờ (Pending)
    pending_orders = Order.query.filter_by(status='pending').order_by(Order.created_at.desc()).all()
    
    orders_list = []
    for order in pending_orders:
        payment_info = json.loads(order.payment_info or '{}')
        bill_image_filename = payment_info.get('bill_image', None)
        detail_info = "Không có dữ liệu"
        
        sell_content = payment_info.get('sell_content', f"{order.id} HOANG NGOC SON transfer") 

        # Biến chứa thông tin bank để tạo QR
        user_bank_raw = None

        if order.mode == 'buy': 
            w = Wallet.query.filter_by(id=order.user_wallet_id).first()
            if w:
                tag_info = f" | Tag: {w.tag}" if w.tag else ""
                detail_info = f"<b>Addr:</b> {w.address}<br><b>Tên:</b> {w.name}{tag_info}"
        else: 
            # Xử lý Đơn Bán -> Lấy thông tin Bank khách
            b = Bank.query.filter_by(id=order.user_bank_id).first()
            if b:
                detail_info = f"<b>Bank:</b> {b.bank_name}<br><b>STK:</b> {b.account_number}<br><b>Tên:</b> {b.account_name}"
                # Tạo dữ liệu raw để JS tạo mã QR
                user_bank_raw = {
                    "bankName": b.bank_name,
                    "accountNo": b.account_number,
                    "accountName": remove_accents(b.account_name),
                    "amount": int(order.amount_vnd),
                    "addInfo": sell_content
                }

        orders_list.append({
            "id": order.id, "mode": order.mode, "coin": order.coin, "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin, "status": order.status, "created_at": order.created_at.isoformat(),
            "username": order.username, 
            "detail_info": detail_info,
            "bill_image": bill_image_filename,
            "sell_content": sell_content,
            "user_bank_raw": user_bank_raw
        })

    # 2. [MỚI] Tính toán thống kê (Bao gồm cả Trọn đời và Tháng này)
    try:
        # --- A. Xác định ngày đầu tháng ---
        today = datetime.now()
        first_day_of_month = datetime(today.year, today.month, 1)

        # --- B. Tính tổng trọn đời (Lifetime) ---
        total_vnd_in = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', Order.mode == 'buy'
        ).scalar() or 0

        total_vnd_out = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', Order.mode == 'sell'
        ).scalar() or 0

        # Tính volume từng loại coin
        total_bustabit = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'bustabit'
        ).scalar() or 0

        total_usdt = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'usdt'
        ).scalar() or 0
        
        total_ether = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'ether'
        ).scalar() or 0

        total_bnb = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'bnb'
        ).scalar() or 0

        total_sol = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'sol'
        ).scalar() or 0

        # --- C. Tính tổng tháng này (Monthly) ---
        total_vnd_in_month = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', 
            Order.mode == 'buy',
            Order.created_at >= first_day_of_month 
        ).scalar() or 0

        total_vnd_out_month = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', 
            Order.mode == 'sell',
            Order.created_at >= first_day_of_month
        ).scalar() or 0

        # Đóng gói dữ liệu trả về
        stats_dict = {
            "total_vnd_in": total_vnd_in,            
            "total_vnd_out": total_vnd_out,           
            "total_vnd_in_month": total_vnd_in_month,   
            "total_vnd_out_month": total_vnd_out_month, 
            
            "total_bustabit_volume": total_bustabit,
            "total_usdt_volume": total_usdt,
            "total_ether_volume": total_ether,
            "total_bnb_volume": total_bnb,
            "total_sol_volume": total_sol
        }
    except Exception as e:
        print(f"Lỗi tính toán thống kê: {e}")
        stats_dict = {}

    return jsonify({"success": True, "transactions": orders_list, "stats": stats_dict})

@app.route("/api/admin/transactions/complete", methods=['POST'])
@admin_required
def complete_admin_transaction():
    user = get_user_from_request()
    
    data = request.json
    order_id = data.get('order_id')
    
    order = Order.query.filter_by(id=order_id).first()
    if not order:
        return jsonify({"success": False, "message": "Không tìm thấy đơn hàng"}), 404
        
    order.status = 'completed' # Cập nhật trạng thái
    db.session.commit()

    try:
        action = "Đã nhận coin" if order.mode == 'buy' else "Đã nhận VNĐ"
        message = (
            f"✅ *ĐƠN HÀNG HOÀN TẤT*\n"
            f"Mã GD: *{order.id}*\n"
            f"User: *{order.username}*\n"
            f"Loại: *{order.mode.upper()}*"
            )
        send_telegram_notification(message, order_id=order.id)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

    socketio.emit('order_completed', {'order_id': order.id}, room=order.id)
    
    return jsonify({"success": True, "message": f"Đã hoàn tất đơn hàng {order_id}"})

# --- [MỚI] API LỊCH SỬ CÔNG KHAI (TRANG CHỦ) ---
@app.route("/api/public-transactions", methods=['GET'])
def get_public_transactions():
    try:
        # Lấy 10 đơn hàng đã hoàn thành, đơn mới nhất lên đầu
        recent_orders = Order.query.filter_by(status='completed').order_by(Order.created_at.desc()).limit(10).all()
        
        orders_list = []
        for order in recent_orders:
            orders_list.append({
                "mode": "Mua" if order.mode == 'buy' else "Bán",
                "coin": "Bustabit" if order.coin == 'bustabit' else "USDT",
                # Chúng ta chỉ gửi 2 chữ số thập phân cho coin để hiển thị
                "amount_coin": round(order.amount_coin, 2), 
                "created_at": order.created_at.strftime("%d/%m/%Y %H:%M") # Định dạng lại ngày
            })
            
        return jsonify({"success": True, "transactions": orders_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
    # ---API ADMIN XEM LỊCH SỬ GIAO DỊCH ĐÃ HOÀN THÀNH ---
@app.route("/api/admin/transactions/history", methods=['GET'])
@admin_required
def get_admin_transactions_history():
    user = get_user_from_request()

    # Lấy tham số từ URL
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Bộ lọc
    filter_username = request.args.get('username')
    filter_coin = request.args.get('coin')
    filter_date_from = request.args.get('date_from')
    filter_date_to = request.args.get('date_to')

    # Query cơ bản
    query = Order.query.filter_by(status='completed')

    # Áp dụng lọc
    if filter_username:
        search_term = f"%{filter_username}%"
        query = query.filter(or_(
            Order.username.ilike(search_term),
            Order.id.ilike(search_term)
        ))
    if filter_coin and filter_coin != 'all':
        query = query.filter(Order.coin == filter_coin)
    if filter_date_from:
        try:
            d_from = datetime.strptime(filter_date_from, '%Y-%m-%d')
            query = query.filter(Order.created_at >= d_from)
        except: pass
    if filter_date_to:
        try:
            d_to = datetime.strptime(filter_date_to, '%Y-%m-%d') + timedelta(days=1) # Đến hết ngày đó
            query = query.filter(Order.created_at < d_to)
        except: pass

    # Sắp xếp và Phân trang
    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    try:
        orders_list = []
        for order in pagination.items:
            orders_list.append({
                "id": order.id,
                "mode": "Mua" if order.mode == 'buy' else "Bán",
                "coin": order.coin.upper(),
                "amount_vnd": order.amount_vnd,
                "amount_coin": order.amount_coin,
                "status": order.status,
                "created_at": order.created_at.strftime("%d/%m/%Y %H:%M"),
                "username": order.username,
                "user_wallet_id": order.user_wallet_id,
                "user_bank_id": order.user_bank_id
            })

        return jsonify({
            "success": True, 
            "transactions": orders_list,
            "pagination": {
                "total_pages": pagination.pages,
                "current_page": page,
                "total_items": pagination.total
            }
        })
    except Exception as e:
        print(f"Lỗi API History: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    
    # ---API ADMIN QUẢN LÝ NGƯỜI DÙNG ---
@app.route("/api/admin/users", methods=['GET'])
@admin_required
def get_admin_all_users():
    user = get_user_from_request()

    try:
        # Lấy tất cả người dùng, trừ chính admin
        all_users = User.query.filter(User.username != user.username).order_by(User.id.asc()).all()

        users_list = []
        for u in all_users:
            users_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                # Đếm số đơn hàng của họ (nếu cần, tạm thời để 0)
                "order_count": Order.query.filter_by(username=u.username).count() 
            })

        return jsonify({"success": True, "users": users_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
# --- [MỚI] API LỊCH SỬ CÁ NHÂN (PROFILE) ---
@app.route("/api/user/my-transactions", methods=['GET'])
def get_user_transactions():
    user = get_user_from_request()
    if not user: 
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401

    try:
        # Lấy tất cả đơn hàng của user này, đơn mới nhất lên đầu
        user_orders = Order.query.filter_by(username=user.username).order_by(Order.created_at.desc()).all()

        orders_list = []
        for order in user_orders:
            # Dịch trạng thái ra Tiếng Việt
            status_vi = "Đã hoàn thành"
            if order.status == 'pending':
                status_vi = "Đang chờ xử lý"
            elif order.status == 'cancelled':
                status_vi = "Đã hủy"

            orders_list.append({
                "id": order.id,
                "mode": "Mua" if order.mode == 'buy' else "Bán",
                "coin": "Bustabit" if order.coin == 'bustabit' else "USDT",
                "amount_vnd": order.amount_vnd,
                "amount_coin": order.amount_coin,
                "status_vi": status_vi,
                "created_at": order.created_at.strftime("%d/%m/%Y %H:%M")
            })

        return jsonify({"success": True, "transactions": orders_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500    
    
@socketio.on('join_room')
def handle_join_room(data):
    """
    Client (người dùng) gọi sự kiện này khi họ mở trang thanh toán
    để tham gia vào phòng của riêng đơn hàng đó.
    """
    room = data.get('room_id')
    if room:
        from flask_socketio import join_room
        join_room(room)
        print(f"✅ Client đã tham gia phòng: {room}")

@socketio.on('connect')
def handle_connect():
    print("Một Client vừa kết nối Socket.IO")

@socketio.on('disconnect')
def handle_disconnect():
    print("Một Client đã ngắt kết nối Socket.IO")

def update_price_task():
    """Cập nhật giá tự động"""
    global current_rates
    try:
        all_prices = price_service.get_all_prices()
        
        if all_prices:
            current_rates = all_prices 
        
        logger.info(f"[INFO] Giá đã cập nhật lúc {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"⚠️ Lỗi cập nhật giá: {e}")

# Hàm kiểm tra ảnh thật
def is_valid_image(file_stream):
    try:
        # Kiểm tra kích thước file
        file_stream.seek(0, 2)  # Di chuyển đến cuối file
        size = file_stream.tell()
        file_stream.seek(0)  # Quay lại đầu
        img = Image.open(file_stream)
        width, height = img.size
        if width > 4000 or height > 4000:  # Chặn ảnh quá lớn
            return False
        
        if size > 5 * 1024 * 1024:  # 5MB
            return False
        
        img = Image.open(file_stream)
        img.verify()
        
        # Kiểm tra định dạng thực
        if img.format not in ['JPEG', 'PNG', 'GIF']:
            return False
        
        file_stream.seek(0)
        return True
    except Exception:
        return False

# CÁC API KYC (XÁC MINH DANH TÍNH)

# 1. User gửi yêu cầu KYC
@app.route("/api/user/submit-kyc", methods=['POST'])
def submit_kyc():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    # Kiểm tra nếu đã có yêu cầu đang chờ hoặc đã duyệt
    existing_kyc = KYC.query.filter_by(user_id=user.id).first()
    if existing_kyc and existing_kyc.status in ['pending', 'approved']:
        return jsonify({"success": False, "message": "Bạn đã gửi yêu cầu hoặc tài khoản đã xác minh."}), 400

    full_name = request.form.get('full_name')
    id_number = request.form.get('id_number')
    
    # Kiểm tra file
    if 'id_front' not in request.files or 'id_back' not in request.files or 'selfie' not in request.files or 'paper' not in request.files:
        return jsonify({"success": False, "message": "Vui lòng tải lên đủ 4 ảnh yêu cầu!"}), 400

    file_front = request.files['id_front']
    if not is_valid_image(file_front):
         return jsonify({"success": False, "message": "File tải lên không hợp lệ hoặc bị lỗi!"}), 400
    file_back = request.files['id_back']
    if not is_valid_image(file_back):
         return jsonify({"success": False, "message": "File tải lên không hợp lệ hoặc bị lỗi!"}), 400
    file_selfie = request.files['selfie']
    if not is_valid_image(file_selfie):
         return jsonify({"success": False, "message": "File tải lên không hợp lệ hoặc bị lỗi!"}), 400
    file_paper = request.files['paper']
    if not is_valid_image(file_paper):
         return jsonify({"success": False, "message": "File tải lên không hợp lệ hoặc bị lỗi!"}), 400

    if not all([allowed_kyc_file(f.filename) for f in [file_front, file_back, file_selfie, file_paper]]):
         return jsonify({"success": False, "message": "Chỉ chấp nhận file ảnh (PNG, JPG, JPEG)"}), 400

    try:
        # Tạo tên file an toàn
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        fname_front = secure_filename(f"{user.username}_{ts}_front.jpg")
        fname_back = secure_filename(f"{user.username}_{ts}_back.jpg")
        fname_selfie = secure_filename(f"{user.username}_{ts}_selfie.jpg")
        fname_paper = secure_filename(f"{user.username}_{ts}_paper.jpg")

        # Lưu file
        file_front.save(os.path.join(KYC_UPLOAD_FOLDER, fname_front))
        file_back.save(os.path.join(KYC_UPLOAD_FOLDER, fname_back))
        file_selfie.save(os.path.join(KYC_UPLOAD_FOLDER, fname_selfie))
        file_paper.save(os.path.join(KYC_UPLOAD_FOLDER, fname_paper))

        # Lưu vào DB (Update nếu bị từ chối trước đó, hoặc tạo mới)
        if existing_kyc:
            existing_kyc.full_name = full_name
            existing_kyc.id_number = id_number
            existing_kyc.id_front_image = fname_front
            existing_kyc.id_back_image = fname_back
            existing_kyc.selfie_image = fname_selfie
            existing_kyc.paper_image = fname_paper
            existing_kyc.status = 'pending'
            existing_kyc.submitted_at = datetime.now()
            existing_kyc.admin_note = None
        else:
            new_kyc = KYC(user_id=user.id, full_name=full_name, id_number=id_number,
                          id_front_image=fname_front, id_back_image=fname_back, selfie_image=fname_selfie, paper_image=fname_paper, status='pending')
            db.session.add(new_kyc)
        
        db.session.commit()

        # Gửi thông báo Telegram cho Admin
        try:
            msg = f"🛡️ *YÊU CẦU KYC MỚI*\nUser: {user.username}\nTên: {full_name}"
            eventlet.spawn(send_telegram_notification, msg)
        except Exception as e:
            print(f"Lỗi tạo task Telegram: {e}")

        return jsonify({"success": True, "message": "Đã gửi hồ sơ KYC thành công! Vui lòng chờ duyệt."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 2. User lấy trạng thái KYC
@app.route("/api/user/kyc-status", methods=['GET'])
def get_kyc_status():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    kyc = KYC.query.filter_by(user_id=user.id).first()
    if not kyc: return jsonify({"success": True, "kyc": None})
    return jsonify({
        "success": True,
        "kyc": {
            "status": kyc.status,
            "admin_note": kyc.admin_note,
            "submitted_at": kyc.submitted_at.strftime("%d/%m/%Y %H:%M")
        }
    })

# 3. Admin lấy danh sách KYC
@app.route("/api/admin/kyc-list", methods=['GET'])
@admin_required
def admin_get_kyc_list():
    user = get_user_from_request()
    
    # Lấy danh sách, sắp xếp pending lên đầu
    reqs = KYC.query.order_by(
        db.case(
            (KYC.status == 'pending', 1),
            (KYC.status == 'approved', 2),
            (KYC.status == 'rejected', 3)
        ),
        KYC.submitted_at.desc()
    ).all()
    
    result = []
    for k in reqs:
        u = User.query.get(k.user_id)
        result.append({
            "id": k.id, 
            "username": u.username if u else "N/A",
            "full_name": k.full_name, 
            "id_number": k.id_number,
            "status": k.status,
            "submitted_at": k.submitted_at.strftime("%d/%m/%Y"),
            "id_front": k.id_front_image, # Tên file ảnh
            "id_back": k.id_back_image,
            "selfie": k.selfie_image,
            "paper": k.paper_image,
            "admin_note": k.admin_note
        })
    return jsonify({"success": True, "requests": result})

# 4. API xem ảnh KYC (Bảo mật: Cho phép Token trên URL cho thẻ img)
@app.route("/api/kyc-image/<path:filename>") 
def serve_kyc_image(filename):
    # Cách 1: Kiểm tra Header (cho Ajax call nếu có)
    user = get_user_from_request()

    # Cách 2: Nếu không có Header, kiểm tra Token trên URL (?token=...)
    if not user:
        token = request.args.get('token')
        if token:
            try:
                payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                username = payload.get('username')
                user = User.query.filter_by(username=username.lower()).first()
            except:
                pass

    # Kiểm tra quyền Admin
    if not user or user.role != 'Admin':
        return "Forbidden", 403
        
    return send_from_directory(KYC_UPLOAD_FOLDER, filename) 

# 5. Admin duyệt/từ chối KYC
@app.route("/api/admin/kyc-review", methods=['POST'])
@admin_required
def admin_review_kyc():
    user = get_user_from_request()
    
    data = request.json
    kyc = KYC.query.get(data.get('kyc_id'))
    if not kyc: return jsonify({"success": False, "message": "Không tìm thấy"}), 404
    
    action = data.get('action')
    kyc.status = 'approved' if action == 'approve' else 'rejected'
    kyc.admin_note = data.get('note', '')
    kyc.reviewed_at = datetime.now()
    db.session.commit()
    
    return jsonify({"success": True, "message": f"Đã {action} yêu cầu KYC."})



@app.route('/')
def serve_index():
    settings = load_settings()
    if settings.get('maintenance_mode') == 'on':
        return render_template('maintenance.html')
    return render_template('index.html')

@app.route('/<path:filename>')
def serve_html(filename):
    settings = load_settings()
    allowed_pages = [
        'login.html', 
        'admin_dashboard.html', 
        'admin_history.html', 
        'admin_users.html', 
        'admin_kyc.html', 
        'admin_spread.html', 
        'admin_settings.html',
        'index.html'
    ]
    if filename.endswith('.html'):
        if settings.get('maintenance_mode') == 'on':
            if filename not in allowed_pages:
                return render_template('maintenance.html')
        
        return render_template(filename)
        
    return "Page not found", 404

def cancel_expired_orders():
    cutoff_time = datetime.now() - timedelta(hours=1)
    expired = Order.query.filter(
        Order.status == 'pending',
        Order.created_at < cutoff_time
    ).all()
    for order in expired:
        order.status = 'cancelled'
    db.session.commit()

@app.route("/api/get-rate-buy-sell", methods=['GET'])
def api_get_rate_buy_sell():
    """
    API: Lấy giá mua/bán tất cả coin 
    Query params: ?coin=btc hoặc không có (lấy tất cả)
    """
    coin = request.args.get('coin', '').lower()
    
    if coin:
        # Lấy 1 coin cụ thể
        rates = price_service.get_rate_buy_sell(coin)
        if rates:
            return jsonify(rates)
        return jsonify({"error": f"Coin {coin} not found"}), 404
    else:
        # Lấy tất cả
        all_prices = price_service.get_all_prices()
        return jsonify({
            "success": True,
            "data": all_prices,
            "timestamp": datetime.now().isoformat()
        })

@app.route("/api/all-prices", methods=['GET'])
def api_all_prices():
    """API: Lấy tất cả giá coin (Format đơn giản)"""
    all_prices = price_service.get_all_prices()
    return jsonify(all_prices)

@app.route("/api/start", methods=['GET'])
def api_start():
    """
    API: Health check + Thông tin hệ thống
    """
    all_prices = price_service.get_all_prices()
    return jsonify({
        "status": "online",
        "service": "Buser Price Service",
        "version": "2.0",
        "data_source": "Binance API + Forex API",
        "available_coins": list(all_prices.keys()),
        "prices": all_prices,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/usd-vnd-rate", methods=['GET'])
def api_usd_vnd_rate():
    """API: Lấy tỷ giá USD/VND hiện tại"""
    rate = price_service.fetch_usd_vnd_rate()
    return jsonify({
        "success": True,
        "rate": rate,
        "format": "1 USD = X VND",
        "timestamp": datetime.now().isoformat()
    })

# API ADMIN: Quản lý Spread

@app.route("/api/admin/update-spread", methods=['POST'])
@admin_required
def admin_update_spread():
    user = get_user_from_request()
    
    data = request.json
    coin = data.get('coin', '').lower()
    buy_percent = float(data.get('buy_percent', 1.5))
    sell_percent = float(data.get('sell_percent', 1.5))
    
    try:
        price_service.update_spread(coin, buy_percent, sell_percent)
        try:
            msg = f"📊 *THAY ĐỔI GIÁ (SPREAD)*\nCoin: {coin.upper()}\nMua: +{buy_percent}%\nBán: -{sell_percent}%"
            send_telegram_notification(msg)
        except: pass
        
        return jsonify({
            "success": True,
            "message": f"Đã cập nhật spread cho {coin}",
            "coin": coin,
            "buy_percent": buy_percent,
            "sell_percent": sell_percent
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/admin/get-spread", methods=['GET'])
@admin_required
def admin_get_spread():
    user = get_user_from_request()
    
    return jsonify({
        "success": True,
        "spread_config": price_service.spread_config
    })

@app.route("/api/site-config", methods=['GET'])
def get_site_config():
    """API lấy thông tin cấu hình công khai (Số dư, Phí)"""
    settings = load_settings()
    return jsonify({
        "success": True,
        "liquidity": {
            "usdt": settings.get('liquidity_usdt', 0),
            "btc": settings.get('liquidity_btc', 0),
            "eth": settings.get('liquidity_eth', 0),
            "bnb": settings.get('liquidity_bnb', 0),
            "sol": settings.get('liquidity_sol', 0)
        },
        "fee_table": settings.get('fee_html_content', '')
    })

# ====================================
# [MỚI] API Debug (Kiểm tra giá raw)
# ====================================

@app.route("/api/debug/crypto-price-usd", methods=['GET'])
def debug_crypto_price_usd():
    """Debug: Xem giá crypto gốc (USD) từ Binance"""
    coin = request.args.get('coin', 'btc').lower()
    price_usd = price_service.get_crypto_price_usd(coin)
    
    if price_usd:
        return jsonify({
            "coin": coin,
            "price_usd": price_usd,
            "source": "Binance API",
            "timestamp": datetime.now().isoformat()
        })
    return jsonify({"error": "Cannot fetch price"}), 500

@app.route("/api/debug/cache-status", methods=['GET'])
def debug_cache_status():
    """Debug: Xem trạng thái cache"""
    with price_service.cache_lock:
        crypto_cache = {}
        for coin, data in price_service.cache['crypto_prices'].items():
            age = (datetime.now() - data['timestamp']).seconds
            crypto_cache[coin] = {
                'price_usd': data['price'],
                'age_seconds': age
            }
        
        usd_vnd_age = None
        if price_service.cache['usd_vnd_timestamp']:
            usd_vnd_age = (datetime.now() - price_service.cache['usd_vnd_timestamp']).seconds
        
        return jsonify({
            "crypto_cache": crypto_cache,
            "usd_vnd_rate": price_service.cache['usd_vnd_rate'],
            "usd_vnd_age_seconds": usd_vnd_age
        })

@app.route("/api/health", methods=['GET'])
def health_check():
    """API kiểm tra trạng thái hệ thống"""
    try:
        # Kiểm tra database
        db.session.execute('SELECT 1')
        
        # Kiểm tra giá
        prices = price_service.get_all_prices()
        
        return jsonify({
            "status": "ok",
            "database": "connected",
            "prices": "active" if len(prices) > 0 else "error",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Chạy máy chủ ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        load_settings()

        
        env_admin_user = os.environ.get('ADMIN_USERNAME')
        env_admin_pass = os.environ.get('ADMIN_PASSWORD')

        admin_user = User.query.filter_by(username=env_admin_user).first()
        if not admin_user:
            hashed_pass = generate_password_hash(env_admin_pass) 
            admin_user = User(
                username=env_admin_user,
                email=f"{env_admin_user}@Buser.ink",
                password=hashed_pass,
                role="Admin",
                is_verified=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f">>> Đã tạo tài khoản Admin ({env_admin_user}/******) từ cấu hình .env <<<")
            
        try:
            update_price_task()
            
            scheduler = BackgroundScheduler()
            # 1. Dọn dẹp bill cũ (24h/lần)
            scheduler.add_job(func=clean_old_bills, trigger="interval", hours=24)
            scheduler.add_job(func=update_price_task, trigger="interval", seconds=60)
            scheduler.add_job(func=cancel_expired_orders, trigger="interval", minutes=15)
            scheduler.start()
            print(">>> Đã kích hoạt: Auto-Clean Bill & Auto-Update Prices")
        except Exception as e:
            print(f" Không thể khởi chạy Scheduler: {e}")
            
print(">>> Khởi chạy Buser-Web server với Socket.IO tại http://127.0.0.1:5000 <<<")
socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=False)