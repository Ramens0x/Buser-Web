import eventlet
eventlet.monkey_patch()
from flask import Flask, jsonify, request, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests 
import json
import os
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

# --- [MỚI] CẤU HÌNH CSDL ---
app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app
)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}, expose_headers=["Authorization"])
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///buser.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-super-secret-key-that-you-should-change')
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Định nghĩa file ---
CONFIG_FILE = "config.json"
API_DOMAIN = "https://bottabot.com"

# --- [MỚI] ĐỊNH NGHĨA CÁC BẢNG CSDL (MODELS) ---
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

# --- Biến tạm ---
current_rates = {'bustabit': {'buy': 0, 'sell': 0}, 'usdt': {'buy': 0, 'sell': 0}}
app_settings = {}

# --- HÀM QUẢN LÝ CÀI ĐẶT ---
def load_settings():
    global app_settings
    if not os.path.exists(CONFIG_FILE):
        default_settings = {"admin_bank_bin": "970407", "admin_account_number": "19035226373011", "admin_account_name": "ADMIN BUSER COM", "admin_bustabit_id": "YOUR_BUSTABIT_ID_HERE", "admin_usdt_wallet": "0x..."}
        save_settings(default_settings)
        app_settings = default_settings
        return default_settings
    try:
        with open(CONFIG_FILE, 'r') as f:
            app_settings = json.load(f); return app_settings
    except json.JSONDecodeError: return app_settings
def save_settings(settings):
    global app_settings
    with open(CONFIG_FILE, 'w') as f: json.dump(settings, f, indent=4)
    app_settings = settings

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

def generate_random_id(prefix="BUSER"):
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

# --- API GIÁ & TÍNH TOÁN (ĐÃ SỬA LỖI THỤT LỀ) ---
@app.route("/api/prices")
def api_get_prices(): 
    global current_rates
    try:
        price_bustabit_buy = requests.get(f"{API_DOMAIN}/get-rate-change-buy/bustabit-bet")
        price_usdt_buy = requests.get(f"{API_DOMAIN}/get-rate-change-buy/win-coin")
        price_bustabit_sell = requests.get(f"{API_DOMAIN}/get-rate-change-sell/bustabit-bet")
        price_usdt_sell = requests.get(f"{API_DOMAIN}/get-rate-change-sell/win-coin")

        if price_bustabit_buy.status_code == 200: current_rates['bustabit']['buy'] = float(price_bustabit_buy.text)
        if price_bustabit_sell.status_code == 200: current_rates['bustabit']['sell'] = float(price_bustabit_sell.text)
        if price_usdt_buy.status_code == 200: current_rates['usdt']['buy'] = float(price_usdt_buy.text)
        if price_usdt_sell.status_code == 200: current_rates['usdt']['sell'] = float(price_usdt_sell.text)
    except Exception as e:
        pass # Bỏ qua lỗi và trả về giá trị cũ (nếu có)
    return jsonify(current_rates)

@app.route("/api/calculate", methods=['POST'])
def api_calculate_swap():
    data = request.json
    amount_in = float(data.get('amount', 0))
    direction = data.get('direction', 'from') 
    mode = data.get('mode', 'sell')
    coin_type = data.get('coin', 'bustabit')
    
    if current_rates[coin_type]['buy'] == 0:
        api_get_prices() # [SỬA LỖI] Gọi đúng tên hàm
        
    amount_out = 0
    
    try:
        if mode == 'buy':
            rate = current_rates[coin_type]['buy']
            if direction == 'from':
                amount_out = amount_in / rate if rate > 0 else 0
            else:
                amount_out = amount_in * rate
        elif mode == 'sell':
            rate = current_rates[coin_type]['sell']
            if direction == 'from':
                amount_out = amount_in * rate
            else:
                amount_out = amount_in / rate if rate > 0 else 0
                
        return jsonify({'amount_out': amount_out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        
        reset_link = f"http://127.0.0.1:5500/reset-password.html?token={token}"
        print(f"--- [EMAIL SIM] Link reset cho {email}: {reset_link} ---")
        
    return jsonify({"success": True, "message": "Nếu email tồn tại, một link đặt lại mật khẩu đã được gửi (Kiểm tra terminal của bạn!)"})

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

# --- API TẠO ĐƠN HÀNG (DÙNG CSDL) ---
@app.route("/api/create-order", methods=['POST'])
def create_order():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    data = request.json
    mode, coin_type = data.get('mode'), data.get('coin')
    amount_from, amount_to = float(data.get('amount_from', 0)), float(data.get('amount_to', 0))
    wallet_id, bank_id = data.get('wallet_id'), data.get('bank_id')
    
    transaction_id = generate_random_id()
    while Order.query.filter_by(id=transaction_id).first():
        transaction_id = generate_random_id()
        
    payment_info_dict = {}
    settings = load_settings()

    if mode == 'buy':
        admin_bin = settings.get('admin_bank_bin'); admin_account = settings.get('admin_account_number'); admin_name = settings.get('admin_account_name')
        viet_qr = VietQR(); viet_qr.set_beneficiary_organization(admin_bin, admin_account); viet_qr.set_transaction_amount(str(int(amount_from))); viet_qr.set_additional_data_field_template(transaction_id);
        qr_data_string = viet_qr.build()
        payment_info_dict = {"bank": f"Bank (BIN: {admin_bin})", "account_number": admin_account, "account_name": admin_name, "amount": int(amount_from), "content": transaction_id, "qr_data_string": qr_data_string}
    else: # mode == 'sell'
        wallet_address = (settings.get('admin_bustabit_id') if coin_type == 'bustabit' else settings.get('admin_usdt_wallet'))
        payment_info_dict = {"memo": "", "wallet_address": wallet_address, "network": "Bustabit" if coin_type == 'bustabit' else "BEP20 (BSC)"}
    
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

    # --- gửi thông báo cho admin ---
    try:
        if new_order.mode == 'buy':
            message = (
                f"🔔 *Đơn MUA Mới (Chờ gửi Coin)*\n"
                f"User: *{new_order.username}*\n"
                f"Nhận VNĐ: *{new_order.amount_vnd:,.0f} VNĐ*\n"
                f"Gửi Coin: *{new_order.amount_coin:.8f} {new_order.coin.upper()}*"
            )
        else:
            message = (
                f"🔔 *Đơn BÁN Mới (Chờ gửi VNĐ)*\n"
                f"User: *{new_order.username}*\n"
                f"Nhận Coin: *{new_order.amount_coin:.8f} {new_order.coin.upper()}*\n"
                f"Gửi VNĐ: *{new_order.amount_vnd:,.0f} VNĐ*"
            )
        send_telegram_notification(message)
    except Exception as e:
        print(f"Lỗi khi tạo tin nhắn Telegram: {e}")

    return jsonify({"success": True, "order": {
        "id": new_order.id, "username": new_order.username, "mode": new_order.mode,
        "coin": new_order.coin, "status": new_order.status, "created_at": new_order.created_at.isoformat(),
        "amount_vnd": new_order.amount_vnd, "amount_coin": new_order.amount_coin,
        "user_wallet_id": new_order.user_wallet_id, "user_bank_id": new_order.user_bank_id,
        "payment_info": payment_info_dict
    }})

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
    
    # Nếu là đơn MUA (Admin nhận tiền), cần tạo lại QR Code string để frontend hiển thị
    # (Lưu ý: Logic này tái sử dụng từ create_order, thực tế nên tách hàm riêng, nhưng để đây cho gọn)
    qr_data_string = ""
    if order.mode == 'buy':
        settings = load_settings()
        admin_bin = settings.get('admin_bank_bin')
        admin_account = settings.get('admin_account_number')
        if admin_bin and admin_account:
             # Tái tạo VietQR object nhanh để lấy string
            viet_qr = VietQR()
            viet_qr.set_beneficiary_organization(admin_bin, admin_account)
            viet_qr.set_transaction_amount(str(int(order.amount_vnd)))
            viet_qr.set_additional_data_field_template(order.id)
            qr_data_string = viet_qr.build()

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

# --- [MỚI] HÀM GỬI THÔNG BÁO TELEGRAM ---
def send_telegram_notification(message):
    global app_settings # Lấy cài đặt toàn cục
    token = app_settings.get('TELEGRAM_BOT_TOKEN')
    chat_id = app_settings.get('TELEGRAM_CHAT_ID')

    # Kiểm tra nếu admin chưa cấu hình
    if not token or not chat_id or token == "TOKEN_CUA_BAN_O_DAY":
        print(">>> LƯU Ý: Chưa cấu hình Telegram Bot. Bỏ qua thông báo.")
        return

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Chúng ta dùng Markdown để tin nhắn đẹp hơn (in đậm)
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown' 
    }

    try:
        # Gửi tin nhắn, timeout 5 giây (để không làm treo web nếu Telegram chậm)
        requests.post(api_url, json=payload, timeout=5)
    except Exception as e:
        # Nếu Telegram lỗi, chỉ in ra console, không làm sập server
        print(f"Lỗi khi gửi thông báo Telegram: {e}")

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
    return jsonify({"success": True, "message": f"Admin đã hủy đơn hàng {order_id}"})

    # --- [MỚI] API ADMIN ĐỂ XEM VÀ DUYỆT GIAO DỊCH ---
@app.route("/api/admin/transactions", methods=['GET'])
def get_admin_transactions():
    user = get_user_from_request()
    if not user or user.role != 'Admin':
        return jsonify({"success": False, "message": "Không có quyền truy cập"}), 403

    # 1. Lấy các đơn hàng "pending" (Như cũ)
    pending_orders = Order.query.filter_by(status='pending').order_by(Order.created_at.desc()).all()

    orders_list = []
    for order in pending_orders:
        orders_list.append({
            "id": order.id,
            "mode": order.mode,
            "coin": order.coin,
            "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
            "username": order.username,
            "user_wallet_id": order.user_wallet_id,
            "user_bank_id": order.user_bank_id
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
    
# --- Chạy máy chủ ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        load_settings()
        
        # Kiểm tra và tạo admin bằng chữ thường
        admin_user = User.query.filter_by(username='buser').first()
        if not admin_user:
            admin_pass = generate_password_hash("sonhoang1") 
            admin_user = User(
                username="buser",
                email="admin@buser.com",
                password=admin_pass,
                role="Admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print(">>> Đã tạo tài khoản Admin (buser/sonhoang1) cố định <<<") 
            
print(">>> Khởi chạy Buser-Web server với Socket.IO tại http://127.0.0.1:5000 <<<")
socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)