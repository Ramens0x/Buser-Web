import eventlet
eventlet.monkey_patch()
from flask import Flask, jsonify, request, send_file
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
from flask_mail import Mail, Message
import time
from apscheduler.schedulers.background import BackgroundScheduler
from flask_migrate import Migrate

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('buser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# --- [MỚI] CẤU HÌNH CSDL ---
app = Flask(__name__, static_folder='static', template_folder='templates')
UPLOAD_FOLDER = 'uploads/bills'
KYC_UPLOAD_FOLDER = 'uploads/kyc'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['KYC_UPLOAD_FOLDER'] = KYC_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Giới hạn 5MB
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Tự tạo thư mục nếu chưa có
os.makedirs(KYC_UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_kyc_file(filename):
    ALLOWED = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def clean_old_bills():
    try:
        retention_period = 90 * 24 * 60 * 60 
        now = time.time()
        folder = app.config.get('UPLOAD_FOLDER')
        if not folder or not os.path.exists(folder): return
        count = 0
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                if now - os.path.getmtime(filepath) > retention_period:
                    os.remove(filepath); count += 1
        if count > 0: print(f"🧹 Đã xóa {count} bill cũ.")
    except Exception as e: print(f"❌ Lỗi dọn dẹp: {e}")

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
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}, expose_headers=["Authorization"])
# Lấy địa chỉ Database từ biến môi trường
database_url = os.environ.get('DATABASE_URL', 'sqlite:///buser.db')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-super-secret-key-that-you-should-change')
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
    wallets = db.relationship('Wallet', backref='owner', lazy=True)
    banks = db.relationship('Bank', backref='owner', lazy=True)
    kyc = db.relationship('KYC', backref='user', uselist=False, lazy=True)

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
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending/approved/rejected
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)

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

# --- HÀM TIỆN ÍCH ---
# Hàm xóa dấu tiếng Việt và viết hoa
def remove_accents(input_str):
    if not input_str: return ""
    s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
    s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
    s = ''
    for c in input_str:
        if c in s1:
            s += s0[s1.index(c)]
        else:
            s += c
    return s.upper()

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
            "liquidity_vnd": 50000000,
            "liquidity_usdt": 10000,
            "liquidity_btc": 1,
            "liquidity_eth": 1,
            "liquidity_bnb": 1,
            "liquidity_sol": 1,
            "coin_fees": {
                "bustabit": 0,  
                "ether": 0,     
                "usdt": 0,      
                "sol": 0,       
                "bnb": 0       
                },
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
            app_settings = json.load(f); return app_settings
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
        msg = Message('Đặt lại mật khẩu - Buser.com',
                      sender=app.config.get('MAIL_USERNAME'),
                      recipients=[user_email])
        msg.body = f'Xin chào,\n\nBạn đã yêu cầu đặt lại mật khẩu. Vui lòng click vào link sau:\n{reset_link}\n\nLink này sẽ hết hạn sau 15 phút.\n\nTrân trọng,\nBuser Team'
        mail.send(msg)
        print(f"✅ Đã gửi email reset tới {user_email}")
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")

# --- HÀM LẤY USER TỪ TOKEN ---
def get_user_from_request():
    auth_header = request.headers.get('Authorization')
    if not auth_header: 
        return None

    try:
        # Tách lấy token từ "Bearer <token>"
        token = auth_header.split(" ")[1]
        if not token:
            return None

        # [MỚI] Giải mã token JWT
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])

        # Lấy username từ bên trong token đã giải mã
        username = payload.get('username')
        if not username:
            return None

        # Trả về user dựa trên username đó
        return User.query.filter_by(username=username.lower()).first()

    except jwt.ExpiredSignatureError:
        # Token đã hết hạn
        return None 
    except jwt.InvalidTokenError:
        # Token không hợp lệ
        return None
    except Exception as e:
        # Các lỗi khác (ví dụ: header không có 'Bearer ')
        return None

def generate_random_id(prefix="Chuyen Tien"):
    number = random.randint(100000, 999999)
    return f"{prefix}{number}"

# --- CLASS VÀ HÀM TẠO VIETQR (ĐÃ SỬA LỖI THỤT LỀ) ---
class VietQR:
    def __init__(self):
        self.payload_format_indicator = "000201"
        self.point_of_initiation_method = "010212"
        self.consumer_account_information = ""
        self.guid = "0010A000000727"
        self.service_code = "0208QRIBFTTA"
        self.transaction_currency = "5303704"
        self.transaction_amount = ""
        self.country_code = "5802VN"
        self.additional_data_field_template = ""
        self.crc = ""

    def convert_length(self, string):
        num = len(string)
        return f"0{num}" if num < 10 else str(num)

    def set_transaction_amount(self, money):
        length = self.convert_length(money)
        self.transaction_amount = f"54{length}{money}"
        return self

    def set_beneficiary_organization(self, acquier_id, consumer_id):
        acquier_length = self.convert_length(acquier_id)
        acquier = f"00{acquier_length}{acquier_id}"
        consumer_length = self.convert_length(consumer_id)
        consumer = f"01{consumer_length}{consumer_id}"
        beneficiary_organization = f"{acquier}{consumer}"
        beneficiary_organization_length = self.convert_length(beneficiary_organization)
        consumer_account_information = f"{self.guid}01{beneficiary_organization_length}{beneficiary_organization}{self.service_code}"
        consumer_account_information_length = self.convert_length(consumer_account_information)
        self.consumer_account_information = f"38{consumer_account_information_length}{consumer_account_information}"
        return self

    def set_additional_data_field_template(self, content):
        content_length = self.convert_length(content)
        additional_data = f"08{content_length}{content}"
        additional_data_field_template_length = self.convert_length(additional_data)
        self.additional_data_field_template = f"62{additional_data_field_template_length}{additional_data}"
        return self

    # [SỬA LỖI] Đã sửa lỗi thụt lề ở đây
    def calc_crc(self, string):
        crc_table=[0x0000,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef,0x1231,0x0210,0x3273,0x2252,0x52b5,0x4294,0x72f7,0x62d6,0x9339,0x8318,0xb37b,0xa35a,0xd3bd,0xc39c,0xf3ff,0xe3de,0x2462,0x3443,0x0420,0x1401,0x64e6,0x74c7,0x44a4,0x5485,0xa56a,0xb54b,0x8528,0x9509,0xe5ee,0xf5cf,0xc5ac,0xd58d,0x3653,0x2672,0x1611,0x0630,0x76d7,0x66f6,0x5695,0x46b4,0xb75b,0xa77a,0x9719,0x8738,0xf7df,0xe7fe,0xd79d,0xc7bc,0x48c4,0x58e5,0x6886,0x78a7,0x0840,0x1861,0x2802,0x3823,0xc9cc,0xd9ed,0xe98e,0xf9af,0x8948,0x9969,0xa90a,0xb92b,0x5af5,0x4ad4,0x7ab7,0x6a96,0x1a71,0x0a50,0x3a33,0x2a12,0xdbfd,0xcbdc,0xfbbf,0xeb9e,0x9b79,0x8b58,0xbb3b,0xab1a,0x6ca6,0x7c87,0x4ce4,0x5cc5,0x2c22,0x3c03,0x0c60,0x1c41,0xedae,0xfd8f,0xcdec,0xddcd,0xad2a,0xbd0b,0x8d68,0x9d49,0x7e97,0x6eb6,0x5ed5,0x4ef4,0x3e13,0x2e32,0x1e51,0x0e70,0xff9f,0xefbe,0xdfdd,0xcffc,0xbf1b,0xaf3a,0x9f59,0x8f78,0x9188,0x81a9,0xb1ca,0xa1eb,0xd10c,0xc12d,0xf14e,0xe16f,0x1080,0x00a1,0x30c2,0x20e3,0x5004,0x4025,0x7046,0x6067,0x83b9,0x9398,0xa3fb,0xb3da,0xc33d,0xd31c,0xe37f,0xf35e,0x02b1,0x1290,0x22f3,0x32d2,0x4235,0x5214,0x6277,0x7256,0xb5ea,0xa5cb,0x95a8,0x8589,0xf56e,0xe54f,0xd52c,0xc50d,0x34e2,0x24c3,0x14a0,0x0481,0x7466,0x6447,0x5424,0x4405,0xa7db,0xb7fa,0x8799,0x97b8,0xe75f,0xf77e,0xc71d,0xd73c,0x26d3,0x36f2,0x0691,0x16b0,0x6657,0x7676,0x4615,0x5634,0xd94c,0xc96d,0xf90e,0xe92f,0x99c8,0x89e9,0xb98a,0xa9ab,0x5844,0x4865,0x7806,0x6827,0x18c0,0x08e1,0x3882,0x28a3,0xcb7d,0xdb5c,0xeb3f,0xfb1e,0x8bf9,0x9bd8,0xabbb,0xbb9a,0x4a75,0x5a54,0x6a37,0x7a16,0x0af1,0x1ad0,0x2ab3,0x3a92,0xfd2e,0xed0f,0xdd6c,0xcd4d,0xbdaa,0xad8b,0x9de8,0x8dc9,0x7c26,0x6c07,0x5c64,0x4c45,0x3ca2,0x2c83,0x1ce0,0x0cc1,0xef1f,0xff3e,0xcf5d,0xdf7c,0xaf9b,0xbfba,0x8fd9,0x9ff8,0x6e17,0x7e36,0x4e55,0x5e74,0x2e93,0x3eb2,0x0ed1,0x1ef0]
        crc=0xffff
        for char in string:
            c=ord(char)
            if c>255:
                raise ValueError("Character out of range")
            j=(c^(crc>>8))&0xff
            crc=crc_table[j]^(crc<<8)
        return crc&0xffff

    def build(self):
        content_qr = (f"{self.payload_format_indicator}{self.point_of_initiation_method}"
                      f"{self.consumer_account_information}{self.transaction_currency}"
                      f"{self.transaction_amount}{self.country_code}"
                      f"{self.additional_data_field_template}6304")
        crc = format(self.calc_crc(content_qr), '04x').upper()
        return f"{content_qr}{crc}"

def generate_qr_code_image(data):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

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
    coin_type = data.get('coin', 'bustabit, ether, usdt, sol, bnb') 
    
    settings = load_settings()
    coin_fees = settings.get('coin_fees', {})
    
    current_fee = float(coin_fees.get(coin_type, 0))

    if current_rates.get(coin_type, {}).get('buy', 0) == 0:
        from price_service import price_service
        all_prices = price_service.get_all_prices()
        if all_prices:
            current_rates.update(all_prices)
        
    amount_out = 0
    
    try:
        if mode == 'buy':
            rate = current_rates[coin_type]['buy']
            if rate > 0:
                if direction == 'from': 
                    net_vnd = amount_in - current_fee
                    if net_vnd < 0: net_vnd = 0
                    amount_out = net_vnd / rate
                else:
                    amount_out = (amount_in * rate) + current_fee

        elif mode == 'sell':
            rate = current_rates[coin_type]['sell']
            if rate > 0:
                if direction == 'from':
                    amount_out = amount_in * rate
                else:
                    amount_out = amount_in / rate
                
        return jsonify({'amount_out': amount_out})
    except Exception as e:
        print(f"Calc Error: {e}")
        return jsonify({"amount_out": 0}), 200

# --- API USER (ĐÃ CẬP NHẬT DÙNG CSDL) ---
@app.route("/api/register", methods=['POST'])
@limiter.limit("10 per hour")
def api_register_user():
    data = request.json
    username_raw, email, password = data.get('username'), data.get('email'), data.get('password') # 1. Lấy tên gốc
    if not all([username_raw, email, password]): 
        return jsonify({"success": False, "message": "Vui lòng nhập đủ thông tin"}), 400
    
    username = username_raw.lower() # 2. *** CHUYỂN SANG CHỮ THƯỜNG ***
    
    if User.query.filter_by(username=username).first(): # 3. Kiểm tra bằng chữ thường
        return jsonify({"success": False, "message": "Tên đăng nhập đã tồn tại"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email đã được sử dụng"}), 400
    
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, email=email, password=hashed_password, role="User") # 4. Lưu bằng chữ thường
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": True, "message": "Đăng ký thành công!"})

@app.route("/api/login", methods=['POST'])
@limiter.limit("20 per minute")
def api_login_user():
    data = request.json
    username_raw, password = data.get('username'), data.get('password')
    if not all([username_raw, password]): 
        return jsonify({"success": False, "message": "Vui lòng nhập đủ thông tin"}), 400
    username = username_raw.lower()
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "Tên đăng nhập không tồn tại"}), 404
        
    if check_password_hash(user.password, password):
        # [MỚI] Tạo token JWT
        # Token sẽ hết hạn sau 24 giờ
        payload = {
            'username': user.username,
            'exp': datetime.now() + timedelta(days=1) 
        }
        # Ký (tạo) token bằng SECRET_KEY
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            "success": True, "message": "Đăng nhập thành công!",
            "user": {"username": user.username, "email": user.email, "role": user.role},
            "token": token
        })
    else:
        return jsonify({"success": False, "message": "Sai mật khẩu"}), 401

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
@limiter.limit("3 per hour") # Chống spam: Chỉ cho gửi 3 mail/giờ/IP
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
@limiter.limit("10 per minute")
def create_order():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    data = request.json
    mode, coin_type = data.get('mode'), data.get('coin')
    amount_from, amount_to = float(data.get('amount_from', 0)), float(data.get('amount_to', 0))
    wallet_id, bank_id = data.get('wallet_id'), data.get('bank_id')

    # Xác định số tiền VNĐ trong giao dịch: Nếu Mua: Khách trả VNĐ (amount_from) Nếu Bán: Khách nhận VNĐ (amount_to)/ Cấu hình hạn mức bắt buộc KYC (100 triệu)
    transaction_vnd = amount_from if mode == 'buy' else amount_to
    KYC_LIMIT = 100000000
    if transaction_vnd > KYC_LIMIT:
        # Kiểm tra xem user đã KYC chưa
        kyc_record = KYC.query.filter_by(user_id=user.id).first()
        
        # Nếu chưa gửi KYC hoặc chưa được duyệt -> Chặn lại
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
            return jsonify({
                "success": False, 
                "message": f"Số lượng mua vượt quá thanh khoản hiện có của hệ thống ({limit:,.4f} {coin_type.upper()})."
            }), 400

    # Mã ngắn (Unique ID) cho Database: T + 8 số ngẫu nhiên
    def get_unique_order_id():
        while True:
            # Tạo chuỗi 8 chữ số ngẫu nhiên
            digits = ''.join([str(random.randint(0, 9)) for _ in range(8)])
            oid = f"T{digits}"
            if not Order.query.filter_by(id=oid).first():
                return oid

    transaction_id = get_unique_order_id() # Ví dụ: T12345678
    # Lấy tên người dùng (để ghép vào nội dung)
    user_account_name = ""

    user_bank = Bank.query.filter_by(user_id=user.id).first()
    if user_bank and user_bank.account_name:
        user_account_name = remove_accents(user_bank.account_name)
    else:
        # Nếu chưa add bank, dùng username viết hoa
        user_account_name = user.username.upper()

    # Nội dung chuyển khoản đầy đủ: T + 8 số + Tên + transfer
    full_transfer_content = f"{transaction_id} {user_account_name} transfer"

        
    payment_info_dict = {}
    settings = load_settings()

    if mode == 'buy':
        admin_banks_list = settings.get('admin_banks', [])
        
        if not admin_banks_list:
            return jsonify({"success": False, "message": "Lỗi hệ thống: Admin chưa cấu hình tài khoản nhận tiền."}), 500
            
        # Chọn ngẫu nhiên 1 tài khoản
        selected_bank = random.choice(admin_banks_list)
        
        admin_bin = selected_bank.get('bin')
        admin_account = selected_bank.get('acc')
        admin_name = selected_bank.get('name')
        bank_label = selected_bank.get('bank_name', 'Ngân hàng')

        viet_qr = VietQR(); viet_qr.set_beneficiary_organization(admin_bin, admin_account); viet_qr.set_transaction_amount(str(int(amount_from))); viet_qr.set_additional_data_field_template(full_transfer_content);
        qr_data_string = viet_qr.build()
        payment_info_dict = {
            "bin": admin_bin,
            "bank_name": bank_label,
            "bank": f"{bank_label} (BIN: {admin_bin})",
            "account_number": admin_account, 
            "account_name": admin_name, 
            "amount": int(amount_from), 
            "content": full_transfer_content, 
            "qr_data_string": qr_data_string
        }
    else: 
        if coin_type == 'bustabit':
            wallet_address = settings.get('admin_bustabit_id')
            network = "Bustabit"
        elif coin_type == 'ether':
            wallet_address = settings.get('admin_ether_id') 
            network = "Ether"
        elif coin_type == 'sol':
            wallet_address = settings.get('admin_sol_wallet')
            network = "Solana"
        elif coin_type == 'bnb':
            wallet_address = settings.get('admin_bnb_wallet')
            network = "BEP-20 (BSC)"
        else: 
            wallet_address = settings.get('admin_usdt_wallet')
            network = "BEP-20 (BSC)"

        payment_info_dict = {
            "memo": "", 
            "wallet_address": wallet_address, 
            "network": network,
            "content": full_transfer_content 
        }
    
    new_order = Order(
        id=transaction_id, username=user.username, mode=mode, coin=coin_type,
        amount_vnd = amount_from if mode == 'buy' else amount_to,
        amount_coin = amount_to if mode == 'buy' else amount_from,
        user_wallet_id = wallet_id,
        user_bank_id = bank_id,
        payment_info = json.dumps(payment_info_dict)
    )
    db.session.add(new_order)
    db.session.commit()

    # --- gửi thông báo cho admin (CHẠY NGẦM) ---
    try:
        if new_order.mode == 'buy':
            message = (
                f"🔔 *Đơn MUA Mới (Chờ gửi Coin)*\n"
                f"Mã: *{new_order.id}*\n"
                f"User: *{new_order.username}*\n"
                f"Nhận VNĐ: *{new_order.amount_vnd:,.0f} VNĐ*\n"
                f"Nội dung CK: `{full_transfer_content}`"
            )
        else:
            message = (
                f"🔔 *Đơn BÁN Mới (Chờ gửi VNĐ)*\n"
                f"Mã: *{new_order.id}*\n"
                f"User: *{new_order.username}*\n"
                f"Nhận Coin: *{new_order.amount_coin:.8f} {new_order.coin.upper()}*\n"
                f"Gửi VNĐ: *{new_order.amount_vnd:,.0f} VNĐ*\n"
                f"Nội dung CK (Admin dùng): `{full_transfer_content}`" 
            )
        eventlet.spawn(send_telegram_notification, message, order_id=new_order.id)
    except Exception as e:
        print(f"Lỗi khi tạo tin nhắn Telegram: {e}")

    return jsonify({"success": True, "order": {
        "id": new_order.id, "username": new_order.username, "mode": new_order.mode,
        "coin": new_order.coin, "status": new_order.status, "created_at": new_order.created_at.isoformat(),
        "amount_vnd": new_order.amount_vnd, "amount_coin": new_order.amount_coin,
        "user_wallet_id": new_order.user_wallet_id, "user_bank_id": new_order.user_bank_id,
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
        filename = secure_filename(f"{order_id}_{user.username}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
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
def get_bill_image(filename):
    user = get_user_from_request()
    if not user or user.role != 'Admin': return "Cấm truy cập", 403
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
def admin_settings():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403
    if request.method == 'GET':
        return jsonify({"success": True, "settings": load_settings()})
    if request.method == 'POST':
        save_settings(request.json)
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

@app.route("/api/user/add-wallet", methods=['POST'])
def add_user_wallet():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
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
def admin_cancel_order():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403
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

    # --- [MỚI] API ADMIN ĐỂ XEM VÀ DUYỆT GIAO DỊCH ---
@app.route("/api/admin/transactions", methods=['GET'])
def get_admin_transactions():
    user = get_user_from_request()
    
    if not user or user.role != 'Admin': return jsonify({"success": False, "message": "Không có quyền"}), 403

    pending_orders = Order.query.filter_by(status='pending').order_by(Order.created_at.desc()).all()
    
    orders_list = []
    for order in pending_orders:
        payment_info = json.loads(order.payment_info or '{}')
        bill_image_filename = payment_info.get('bill_image', None)
        detail_info = "Không có dữ liệu"
        if order.mode == 'buy': 
            w = Wallet.query.filter_by(id=order.user_wallet_id).first()
            if w:
                tag_info = f" | Tag: {w.tag}" if w.tag else ""
                detail_info = f"<b>Addr:</b> {w.address}<br><b>Tên:</b> {w.name}{tag_info}"
        else: # Khách bán -> Admin cần biết bank khách để trả tiền
            b = Bank.query.filter_by(id=order.user_bank_id).first()
            if b:
                detail_info = f"<b>Bank:</b> {b.bank_name}<br><b>STK:</b> {b.account_number}<br><b>Tên:</b> {b.account_name}"
        orders_list.append({
            "id": order.id, "mode": order.mode, "coin": order.coin, "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin, "status": order.status, "created_at": order.created_at.isoformat(),
            "username": order.username, 
            "detail_info": detail_info,
            "username": order.username, 
            "detail_info": detail_info,
            "bill_image": bill_image_filename
        })

    # 2. [MỚI] Tính toán thống kê
    try:
        total_vnd_in = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', Order.mode == 'buy'
        ).scalar() or 0

        total_vnd_out = db.session.query(func.sum(Order.amount_vnd)).filter(
            Order.status == 'completed', Order.mode == 'sell'
        ).scalar() or 0

        total_bustabit = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'bustabit'
        ).scalar() or 0

        total_usdt = db.session.query(func.sum(Order.amount_coin)).filter(
            Order.status == 'completed', Order.coin == 'usdt'
        ).scalar() or 0

        stats_dict = {
            "total_vnd_in": total_vnd_in,
            "total_vnd_out": total_vnd_out,
            "total_bustabit_volume": total_bustabit,
            "total_usdt_volume": total_usdt
        }
    except Exception as e:
        print(f"Lỗi tính toán thống kê: {e}")
        stats_dict = {}
    return jsonify({"success": True, "transactions": orders_list, "stats": stats_dict})

@app.route("/api/admin/transactions/complete", methods=['POST'])
def complete_admin_transaction():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403
    
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
    
    # --- [MỚI] API ADMIN XEM LỊCH SỬ GIAO DỊCH ĐÃ HOÀN THÀNH ---
@app.route("/api/admin/transactions/history", methods=['GET'])
def get_admin_transactions_history():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403

    try:
        # Lấy các đơn hàng "completed", mới nhất lên đầu
        completed_orders = Order.query.filter_by(status='completed').order_by(Order.created_at.desc()).all()

        orders_list = []
        for order in completed_orders:
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

        return jsonify({"success": True, "transactions": orders_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
    # --- [MỚI] API ADMIN QUẢN LÝ NGƯỜI DÙNG ---
@app.route("/api/admin/users", methods=['GET'])
def get_admin_all_users():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403

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
    if 'id_front' not in request.files or 'id_back' not in request.files or 'selfie' not in request.files:
        return jsonify({"success": False, "message": "Vui lòng tải lên đủ 3 ảnh"}), 400

    file_front = request.files['id_front']
    if not is_valid_image(file_front):
         return jsonify({"success": False, "message": "File mặt trước không phải là ảnh hợp lệ!"}), 400
    file_back = request.files['id_back']
    if not is_valid_image(file_back):
         return jsonify({"success": False, "message": "File mặt trước không phải là ảnh hợp lệ!"}), 400
    file_selfie = request.files['selfie']
    if not is_valid_image(file_selfie):
         return jsonify({"success": False, "message": "File mặt trước không phải là ảnh hợp lệ!"}), 400

    if not all([allowed_kyc_file(f.filename) for f in [file_front, file_back, file_selfie]]):
         return jsonify({"success": False, "message": "Chỉ chấp nhận file ảnh (PNG, JPG, JPEG)"}), 400

    try:
        # Tạo tên file an toàn
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        fname_front = secure_filename(f"{user.username}_{ts}_front.jpg")
        fname_back = secure_filename(f"{user.username}_{ts}_back.jpg")
        fname_selfie = secure_filename(f"{user.username}_{ts}_selfie.jpg")

        # Lưu file
        file_front.save(os.path.join(KYC_UPLOAD_FOLDER, fname_front))
        file_back.save(os.path.join(KYC_UPLOAD_FOLDER, fname_back))
        file_selfie.save(os.path.join(KYC_UPLOAD_FOLDER, fname_selfie))

        # Lưu vào DB (Update nếu bị từ chối trước đó, hoặc tạo mới)
        if existing_kyc:
            existing_kyc.full_name = full_name
            existing_kyc.id_number = id_number
            existing_kyc.id_front_image = fname_front
            existing_kyc.id_back_image = fname_back
            existing_kyc.selfie_image = fname_selfie
            existing_kyc.status = 'pending'
            existing_kyc.submitted_at = datetime.now()
            existing_kyc.admin_note = None
        else:
            new_kyc = KYC(user_id=user.id, full_name=full_name, id_number=id_number,
                          id_front_image=fname_front, id_back_image=fname_back, selfie_image=fname_selfie, status='pending')
            db.session.add(new_kyc)
        
        db.session.commit()

        # Gửi thông báo Telegram cho Admin
        try:
            msg = f"🛡️ *YÊU CẦU KYC MỚI*\nUser: {user.username}\nTên: {full_name}"
            send_telegram_notification(msg)
        except: pass

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
def admin_get_kyc_list():
    user = get_user_from_request()
    if not user or user.role != 'Admin': return jsonify({"success": False, "message": "Cấm truy cập"}), 403
    
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
def admin_review_kyc():
    user = get_user_from_request()
    if not user or user.role != 'Admin': return jsonify({"success": False}), 403
    
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

@app.route("/api/bitcoin", methods=['GET'])
def api_bitcoin_price():
    """API: Lấy giá Bitcoin (BTC) theo VND"""
    rates = price_service.get_rate_buy_sell('btc')
    if rates:
        return jsonify({
            "success": True,
            "coin": "Bitcoin (BTC)",
            "buy": rates['buy'],
            "sell": rates['sell'],
            "mid": (rates['buy'] + rates['sell']) / 2,
            "timestamp": rates['timestamp']
        })
    return jsonify({"success": False, "message": "Không thể lấy giá BTC"}), 500

@app.route("/api/usdt", methods=['GET'])
def api_usdt_price():
    """API: Lấy giá USDT theo VND"""
    rates = price_service.get_rate_buy_sell('usdt')
    if rates:
        return jsonify({
            "success": True,
            "coin": "USDT",
            "buy": rates['buy'],
            "sell": rates['sell'],
            "mid": (rates['buy'] + rates['sell']) / 2,
            "timestamp": rates['timestamp']
        })
    return jsonify({"success": False, "message": "Không thể lấy giá USDT"}), 500

@app.route("/api/ethereum", methods=['GET'])
@app.route("/api/eth", methods=['GET'])
def api_eth_price():
    """API: Lấy giá Ethereum (ETH) theo VND"""
    rates = price_service.get_rate_buy_sell('eth')
    if rates:
        return jsonify({
            "success": True,
            "coin": "Ethereum (ETH)",
            "buy": rates['buy'],
            "sell": rates['sell'],
            "mid": (rates['buy'] + rates['sell']) / 2,
            "timestamp": rates['timestamp']
        })
    return jsonify({"success": False, "message": "Không thể lấy giá ETH"}), 500

@app.route("/api/bnb", methods=['GET'])
def api_bnb_price():
    """API: Lấy giá BNB theo VND"""
    rates = price_service.get_rate_buy_sell('bnb')
    if rates:
        return jsonify({
            "success": True,
            "coin": "BNB",
            "buy": rates['buy'],
            "sell": rates['sell'],
            "mid": (rates['buy'] + rates['sell']) / 2,
            "timestamp": rates['timestamp']
        })
    return jsonify({"success": False, "message": "Không thể lấy giá BNB"}), 500

@app.route("/api/doge", methods=['GET'])
def api_doge_price():
    """API: Lấy giá Dogecoin theo VND"""
    rates = price_service.get_rate_buy_sell('doge')
    if rates:
        return jsonify({
            "success": True,
            "coin": "Dogecoin (DOGE)",
            "buy": rates['buy'],
            "sell": rates['sell'],
            "mid": (rates['buy'] + rates['sell']) / 2,
            "timestamp": rates['timestamp']
        })
    return jsonify({"success": False, "message": "Không thể lấy giá DOGE"}), 500

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
def admin_update_spread():
    """API Admin: Cập nhật spread cho coin"""
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền"}), 403
    
    data = request.json
    coin = data.get('coin', '').lower()
    buy_percent = float(data.get('buy_percent', 1.5))
    sell_percent = float(data.get('sell_percent', 1.5))
    
    try:
        price_service.update_spread(coin, buy_percent, sell_percent)
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
def admin_get_spread():
    """API Admin: Xem spread hiện tại"""
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền"}), 403
    
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
            "vnd": settings.get('liquidity_vnd', 0),
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
                email=f"{env_admin_user}@buser.com",
                password=hashed_pass,
                role="Admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f">>> Đã tạo tài khoản Admin ({env_admin_user}/******) từ cấu hình .env <<<")
            
        try:
            update_price_task()
            
            scheduler = BackgroundScheduler()
            # 1. Dọn dẹp bill cũ (24h/lần)
            scheduler.add_job(func=clean_old_bills, trigger="interval", hours=24)
            scheduler.add_job(func=update_price_task, trigger="interval", seconds=30)
            scheduler.add_job(func=cancel_expired_orders, trigger="interval", minutes=15)
            scheduler.start()
            print(">>> Đã kích hoạt: Auto-Clean Bill & Auto-Update Prices")
        except Exception as e:
            print(f" Không thể khởi chạy Scheduler: {e}")
            
print(">>> Khởi chạy Buser-Web server với Socket.IO tại http://127.0.0.1:5000 <<<")
socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=False)