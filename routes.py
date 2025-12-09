from flask import Blueprint, request, jsonify, render_template, send_file, send_from_directory, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func, case
from datetime import datetime, timedelta
import os
import json
import secrets
import random
import io
import jwt
import eventlet
import time
from flask_wtf.csrf import generate_csrf
from flask_limiter.util import get_remote_address

# Import các thành phần từ file khác
from extensions import db, socketio, limiter, mail
from models import User, Wallet, Bank, KYC, Order
from helpers import (
    load_settings, save_settings, get_user_from_request, admin_required, 
    send_telegram_notification, save_secure_image, is_valid_image, 
    allowed_file, allowed_kyc_file, send_reset_email, send_async_email,
    current_rates, app_settings
)
from utils import VietQR, generate_qr_code_image, remove_accents
from price_service import price_service
from flask_mail import Message

# Tạo Blueprint (đại diện cho app chính)
bp = Blueprint('main', __name__)

ALLOWED_COINS = ['bustabit', 'ether', 'usdt', 'bnb', 'sol', 'btc', 'eth']

# --- CÁC ROUTE (API) ---

@bp.route("/api/config/supported-banks", methods=['GET'])
def get_supported_banks():
    settings = load_settings()
    return jsonify({"success": True, "banks": settings.get('supported_banks', [])})

@bp.route("/api/prices")
def api_get_prices(): 
    # Cập nhật giá từ service nếu cần
    if current_rates.get('bustabit', {}).get('buy', 0) == 0:
        all_prices = price_service.get_all_prices()
        if all_prices:
            current_rates.update(all_prices)
    return jsonify(current_rates)

@bp.route("/api/calculate", methods=['POST'])
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
        current_app.logger.error(f"Calc Error: {e}", exc_info=True)
        return jsonify({"amount_out": 0}), 200

@bp.route("/api/register", methods=['POST'])
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
    verify_token = secrets.token_hex(20)
    
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
                      sender=current_app.config.get('MAIL_USERNAME'),
                      recipients=[email])
        msg.body = f"Chào {username},\n\nVui lòng click vào link sau để kích hoạt tài khoản:\n{link}\n\nCảm ơn!"
        
        # Dùng _get_current_object() để pass app context vào thread
        eventlet.spawn(send_async_email, current_app._get_current_object(), msg)
        
    except Exception as e:
        current_app.logger.error(f"Lỗi setup gửi mail: {e}", exc_info=True)
    
    return jsonify({"success": True, "message": "Đăng ký thành công! Vui lòng kiểm tra Email để kích hoạt tài khoản."})

@bp.route("/api/verify-email/<token>", methods=['GET'])
def verify_email_token(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return "<h3>Lỗi: Link xác thực không hợp lệ hoặc đã hết hạn!</h3>", 400
    
    if user.is_verified:
        return "<h3>Tài khoản đã được xác thực trước đó. <a href='/login.html'>Đăng nhập ngay</a></h3>"
        
    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    return "<h3>✅ Xác thực thành công! Bạn có thể <a href='/login.html'>Đăng nhập ngay</a></h3>"

@bp.route("/api/login", methods=['POST'])
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
        payload = {
            'username': user.username,
            'exp': datetime.now() + timedelta(hours=2) 
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

        response = jsonify({
            "success": True, 
            "message": "Đăng nhập thành công!",
            "user": {"username": user.username, "email": user.email, "role": user.role}
        })
        
        response.set_cookie(
            'access_token', 
            token, 
            httponly=True,
            secure=True, 
            samesite='Strict',
            max_age=2*60*60
        )
        return response
    else:
        return jsonify({"success": False, "message": "Sai mật khẩu"}), 401

@bp.route("/api/logout", methods=['POST'])
def api_logout():
    response = jsonify({"success": True, "message": "Đăng xuất thành công"})
    response.set_cookie('access_token', '', expires=0)
    return response

@bp.route("/api/change-password", methods=['POST'])
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

@bp.route("/api/change-email", methods=['POST'])
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

@bp.route("/api/forgot-password", methods=['POST'])
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
        
        domain = request.host_url.rstrip('/')
        reset_link = f"{domain}/reset-password.html?token={token}"
        send_reset_email(email, reset_link)
        
    return jsonify({"success": True, "message": "Nếu email tồn tại, vui lòng kiểm tra hộp thư (kể cả mục Spam)."})

@bp.route("/api/reset-password", methods=['POST'])
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

@bp.route("/api/send-contact", methods=['POST'])
@limiter.limit("5 per hour")
def send_contact_email():
    data = request.json
    name = data.get('name')
    user_email = data.get('email')
    subject = data.get('subject')
    message_content = data.get('message')
    
    if not all([name, user_email, subject, message_content]):
        return jsonify({"success": False, "message": "Vui lòng điền đầy đủ thông tin"}), 400
        
    try:
        admin_email = current_app.config['MAIL_USERNAME']
        msg = Message(
            subject=f"[LIÊN HỆ BUSER] {subject}",
            sender=admin_email,
            recipients=[admin_email],
            reply_to=user_email
        )
        msg.body = f"📩 TIN NHẮN TỪ {name} ({user_email}):\n\n{message_content}"
        mail.send(msg)
        return jsonify({"success": True, "message": "Đã gửi liên hệ thành công"})
        
    except Exception as e:
        current_app.logger.error(f"Lỗi gửi mail liên hệ: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Lỗi server, vui lòng thử lại sau"}), 500

# Hàm xác định key để limit (Ưu tiên User ID, nếu không có thì dùng IP)
def rate_limit_key():
    user = get_user_from_request()
    return str(user.id) if user else get_remote_address()

@bp.route("/api/create-order", methods=['POST'])
@limiter.limit("5 per minute", key_func=rate_limit_key)
def create_order():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Vui lòng đăng nhập"}), 401

    data = request.json
    if not data: return jsonify({"success": False, "message": "Dữ liệu không hợp lệ"}), 400
    
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
                "message": f"Giao dịch > {KYC_LIMIT:,.0f} VNĐ yêu cầu KYC!"
            }), 403
    
    # 1. Load cài đặt ngay đầu hàm để dùng chung
    settings = load_settings()

    if mode == 'buy':
        limit = 0
        if coin_type in ['bustabit', 'btc']: limit = float(settings.get('liquidity_btc', 0))
        elif coin_type == 'usdt': limit = float(settings.get('liquidity_usdt', 0))
        elif coin_type in ['ether', 'eth']: limit = float(settings.get('liquidity_eth', 0))
        elif coin_type == 'bnb': limit = float(settings.get('liquidity_bnb', 0))
        elif coin_type == 'sol': limit = float(settings.get('liquidity_sol', 0))
        else: limit = 1000000 
        
        if amount_to > limit:
            return jsonify({"success": False, "message": f"Số lượng mua vượt quá thanh khoản ({limit:,.4f} {coin_type.upper()})."}), 400

    def get_unique_order_id():
        while True:
            digits = ''.join([str(random.randint(0, 9)) for _ in range(8)])
            oid = f"T{digits}"
            if not Order.query.filter_by(id=oid).first(): return oid

    transaction_id = get_unique_order_id() 
    
    # --- Lấy tên người dùng ---
    user_account_name = ""
    kyc_info = KYC.query.filter_by(user_id=user.id).first()
    if kyc_info and kyc_info.full_name:
        user_account_name = remove_accents(kyc_info.full_name)
    else:
        if wallet_id:
            selected_wallet = Wallet.query.filter_by(id=wallet_id).first()
            if selected_wallet and selected_wallet.name:
                user_account_name = remove_accents(selected_wallet.name)
        if not user_account_name and bank_id:
            selected_bank = Bank.query.filter_by(id=bank_id).first()
            if selected_bank and selected_bank.account_name:
                user_account_name = remove_accents(selected_bank.account_name)

        if not user_account_name:
            return jsonify({"success": False, "message": "Vui lòng cập nhật Họ và Tên trong Ví hoặc Ngân hàng."}), 400
            
    transfer_keywords = ["ck tien", "chuyen tien", "hoan tien", "chuyen khoan", "gui tien", "thanh toan", "tra tien hang"]
    random_suffix = random.choice(transfer_keywords)

    # Nội dung CK cho khách chuyển (Đơn Mua)
    full_transfer_content = f"{transaction_id} {user_account_name} {random_suffix}"
    
    # --- [LOGIC MỚI] XỬ LÝ CHỌN BANK ADMIN & TẠO NỘI DUNG ---
    admin_banks = settings.get('admin_banks', [])
    selected_admin_bank = None
    admin_name_for_content = "ADMIN"

    if admin_banks and len(admin_banks) > 0:
        # Chọn ngẫu nhiên 1 ngân hàng
        selected_admin_bank = random.choice(admin_banks)
        # Lấy tên chủ tài khoản từ chính ngân hàng đó
        if selected_admin_bank.get('name'):
            admin_name_for_content = remove_accents(selected_admin_bank.get('name')).upper()
        
    # Tạo nội dung CK cho Admin (Đơn Bán): Mã GD + Tên Admin Random + Suffix Random
    sell_transfer_content = f"{transaction_id} {admin_name_for_content} {random_suffix}"
    # --------------------------------------------------------

    payment_info_dict = {}

    if mode == 'buy':
        if not selected_admin_bank:
            return jsonify({"success": False, "message": "Lỗi hệ thống: Admin chưa cấu hình Bank."}), 500
            
        # Sử dụng thông tin từ bank đã chọn ngẫu nhiên ở trên
        admin_bin = selected_admin_bank.get('bin')
        admin_account = selected_admin_bank.get('acc')
        admin_name = selected_admin_bank.get('name')
        bank_label = selected_admin_bank.get('bank_name', 'Ngân hàng')

        viet_qr = VietQR()
        viet_qr.set_beneficiary_organization(admin_bin, admin_account)
        viet_qr.set_transaction_amount(str(int(amount_from)))
        viet_qr.set_additional_data_field_template(full_transfer_content)
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
        if coin_type == 'bustabit': wallet_address = settings.get('admin_bustabit_id'); network = "Bustabit"
        elif coin_type == 'ether': wallet_address = settings.get('admin_ether_id'); network = "Ether"
        elif coin_type == 'sol': wallet_address = settings.get('admin_sol_wallet'); network = "Solana"
        elif coin_type == 'bnb': wallet_address = settings.get('admin_bnb_wallet'); network = "BEP-20 (BSC)"
        else: wallet_address = settings.get('admin_usdt_wallet'); network = "BEP-20 (BSC)"

        user_bank_snapshot = {}
        if bank_id:
            u_bank = Bank.query.filter_by(id=bank_id).first()
            if u_bank:
                user_bank_snapshot = {
                    "bank_name": u_bank.bank_name,
                    "account_number": u_bank.account_number,
                    "account_name": u_bank.account_name
                }
        payment_info_dict = {
            "memo": "", 
            "wallet_address": wallet_address, 
            "network": network,
            "content": full_transfer_content,
            "sell_content": sell_transfer_content, # Nội dung đã được update theo yêu cầu
            "user_bank_snapshot": user_bank_snapshot
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

    try:
        if new_order.mode == 'buy':
            message = f"🔔 *Đơn MUA Mới*\nMã: *{new_order.id}*\nUser: *{new_order.username}*\nVNĐ: *{new_order.amount_vnd:,.0f}*\nND: `{full_transfer_content}`"
        else:
            message = f"🔔 *Đơn BÁN Mới*\nMã: *{new_order.id}*\nUser: *{new_order.username}*\nCoin: *{new_order.amount_coin:.8f}*\nVNĐ: *{new_order.amount_vnd:,.0f}*\nND Admin CK: `{sell_transfer_content}`"
        eventlet.spawn(send_telegram_notification, message, order_id=new_order.id)
    except Exception as e: current_app.logger.error(f"Lỗi Telegram: {e}", exc_info=True)

    return jsonify({"success": True, "order": {
        "id": new_order.id, "username": new_order.username, "mode": new_order.mode,
        "coin": new_order.coin, "status": new_order.status, "created_at": new_order.created_at.isoformat(),
        "amount_vnd": new_order.amount_vnd, "amount_coin": new_order.amount_coin,
        "payment_info": payment_info_dict
    }})

@bp.route("/api/upload-bill", methods=['POST'])
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
        filename = save_secure_image(file, current_app.config['UPLOAD_FOLDER'], prefix)
        
        if not filename:
            return jsonify({"success": False, "message": "Lỗi khi xử lý ảnh."}), 500
        
        order = Order.query.filter_by(id=order_id, username=user.username).first()
        if order:
            payment_info = json.loads(order.payment_info or '{}')
            payment_info['bill_image'] = filename
            order.payment_info = json.dumps(payment_info)
            db.session.commit()
            
            try:
                msg = f"📸 *BILL MỚI* \nUser: {user.username}\nĐơn: {order_id}"
                send_telegram_notification(msg, order_id=order.id)
            except: pass

            return jsonify({"success": True, "filename": filename, "message": "Đã tải ảnh lên thành công!"})
    return jsonify({"success": False, "message": "File không hợp lệ"}), 400

@bp.route("/api/admin/bill/<path:filename>")
@admin_required
def get_bill_image(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@bp.route("/api/order/<order_id>", methods=['GET'])
def get_order_detail(order_id):
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401

    order = Order.query.filter_by(id=order_id).first()
    if not order: return jsonify({"success": False, "message": "Không tìm thấy đơn hàng"}), 404

    if user.role != 'Admin' and order.username != user.username:
        return jsonify({"success": False, "message": "Bạn không có quyền xem đơn này"}), 403

    payment_info = json.loads(order.payment_info) if order.payment_info else {}
    
    qr_data_string = payment_info.get('qr_data_string', "")
    if order.mode == 'buy' and not qr_data_string:
        admin_bin = payment_info.get('bin')
        admin_account = payment_info.get('account_number')
        if admin_bin and admin_account:
            try:
                viet_qr = VietQR()
                viet_qr.set_beneficiary_organization(admin_bin, admin_account)
                viet_qr.set_transaction_amount(str(int(order.amount_vnd)))
                viet_qr.set_additional_data_field_template(order.id)
                qr_data_string = viet_qr.build()
            except Exception as e: current_app.logger.error(f"Error rebuilding QR: {e}", exc_info=True)

    return jsonify({
        "success": True,
        "order": {
            "id": order.id, "username": order.username, "mode": order.mode,
            "coin": order.coin, "status": order.status, "created_at": order.created_at.isoformat(),
            "amount_vnd": order.amount_vnd, "amount_coin": order.amount_coin,
            "user_wallet_id": order.user_wallet_id, "user_bank_id": order.user_bank_id,
            "payment_info": payment_info, "qr_data_string": qr_data_string 
        }
    })

@bp.route("/api/admin/settings", methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'GET':
        settings = load_settings().copy() 
        if settings.get('TELEGRAM_BOT_TOKEN'):
            settings['TELEGRAM_BOT_TOKEN'] = settings['TELEGRAM_BOT_TOKEN'][:5] + "******" 
        return jsonify({"success": True, "settings": settings})
    if request.method == 'POST':
        save_settings(request.json)
        return jsonify({"success": True, "message": "Cài đặt đã được lưu!"})

@bp.route("/api/generate-qr")
def get_qr_image():
    data = request.args.get('data', '')
    if not data: return "Missing data", 400
    img = generate_qr_code_image(data); img_io = io.BytesIO(); img.save(img_io, 'PNG'); img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@bp.route("/api/user/wallets", methods=['GET'])
def get_user_wallets():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    coin_type = request.args.get('coin_type', 'bustabit')
    wallets = Wallet.query.filter_by(user_id=user.id, coin_type=coin_type).all()
    wallets_list = [{"id": w.id, "coin_type": w.coin_type, "address": w.address, "tag": w.tag, "name": w.name, "phone": w.phone} for w in wallets]
    return jsonify({"success": True, "wallets": wallets_list})

@bp.route("/api/user/add-wallet", methods=['POST'])
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

@bp.route("/api/user/delete-wallet", methods=['POST'])
def delete_user_wallet():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    wallet_id = data.get('wallet_id')
    wallet_to_delete = Wallet.query.filter_by(id=wallet_id, user_id=user.id).first()
    if not wallet_to_delete:
        return jsonify({"success": False, "message": "Không tìm thấy ví"}), 404
    db.session.delete(wallet_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã xóa ví thành công!"})

@bp.route("/api/user/banks", methods=['GET'])
def get_user_banks():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    banks = Bank.query.filter_by(user_id=user.id).all()
    banks_list = [{"id": b.id, "bank_name": b.bank_name, "account_number": b.account_number, "account_name": b.account_name} for b in banks]
    return jsonify({"success": True, "banks": banks_list})

@bp.route("/api/user/add-bank", methods=['POST'])
def add_user_bank():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    data = request.json
    account_number = data.get('account_number', '').strip()
    account_name = data.get('account_name', '').strip().upper()

    if not account_number.isdigit() or len(account_number) < 6 or len(account_number) > 20:
        return jsonify({"success": False, "message": "Số tài khoản không hợp lệ"}), 400
    
    new_bank = Bank(
        bank_name=data.get('bank_name'),
        account_number=account_number,
        account_name=account_name,
        user_id=user.id
    )
    db.session.add(new_bank)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã thêm ngân hàng thành công!"})

@bp.route("/api/user/delete-bank", methods=['POST'])
def delete_user_bank():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    data = request.json
    bank_id = data.get('bank_id')
    bank_to_delete = Bank.query.filter_by(id=bank_id, user_id=user.id).first()
    if not bank_to_delete:
        return jsonify({"success": False, "message": "Không tìm thấy"}), 404
    db.session.delete(bank_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": "Đã xóa ngân hàng thành công!"})

@bp.route("/api/user/cancel-order", methods=['POST'])
def user_cancel_order():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    data = request.json
    order_id = data.get('order_id')
    order = Order.query.filter_by(id=order_id, username=user.username, status='pending').first()
    if not order:
        return jsonify({"success": False, "message": "Không tìm thấy đơn hàng"}), 404
    order.status = 'cancelled'
    db.session.commit()
    return jsonify({"success": True, "message": "Đã hủy đơn hàng thành công!"})

@bp.route("/api/admin/cancel-order", methods=['POST'])
@admin_required
def admin_cancel_order():
    data = request.json
    order_id = data.get('order_id')
    order = Order.query.filter_by(id=order_id, status='pending').first()
    if not order: return jsonify({"success": False, "message": "Không tìm thấy"}), 404
    order.status = 'cancelled'
    db.session.commit()
    socketio.emit('order_completed', {'order_id': order.id}, room=order.id)
    return jsonify({"success": True, "message": f"Admin đã hủy đơn hàng {order_id}"})

@bp.route("/api/admin/transactions", methods=['GET'])
@admin_required
def get_admin_transactions():
    pending_orders = Order.query.filter_by(status='pending').order_by(Order.created_at.desc()).all()
    
    orders_list = []
    for order in pending_orders:
        payment_info = json.loads(order.payment_info or '{}')
        bill_image_filename = payment_info.get('bill_image', None)
        detail_info = "Không có dữ liệu"
        sell_content = payment_info.get('sell_content', f"{order.id} HOANG NGOC SON transfer") 
        user_bank_raw = None

        if order.mode == 'buy': 
            w = Wallet.query.filter_by(id=order.user_wallet_id).first()
            if w:
                tag_info = f" | Tag: {w.tag}" if w.tag else ""
                detail_info = f"<b>Addr:</b> {w.address}<br><b>Tên:</b> {w.name}{tag_info}"
        else: 
            b = Bank.query.filter_by(id=order.user_bank_id).first()
            if b:
                detail_info = f"<b>Bank:</b> {b.bank_name}<br><b>STK:</b> {b.account_number}<br><b>Tên:</b> {b.account_name}"
                user_bank_raw = {
                    "bankName": b.bank_name, "accountNo": b.account_number,
                    "accountName": remove_accents(b.account_name),
                    "amount": int(order.amount_vnd), "addInfo": sell_content
                }

        orders_list.append({
            "id": order.id, "mode": order.mode, "coin": order.coin, "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin, "status": order.status, "created_at": order.created_at.isoformat(),
            "username": order.username, "detail_info": detail_info, "bill_image": bill_image_filename,
            "sell_content": sell_content, "user_bank_raw": user_bank_raw
        })

    # Stats logic
    try:
        today = datetime.now()
        first_day_of_month = datetime(today.year, today.month, 1)
        total_vnd_in = db.session.query(func.sum(Order.amount_vnd)).filter(Order.status == 'completed', Order.mode == 'buy').scalar() or 0
        total_vnd_out = db.session.query(func.sum(Order.amount_vnd)).filter(Order.status == 'completed', Order.mode == 'sell').scalar() or 0
        
        # Volumes per coin
        vols = {}
        for c in ['bustabit', 'usdt', 'ether', 'bnb', 'sol']:
            vols[f"total_{c}_volume"] = db.session.query(func.sum(Order.amount_coin)).filter(Order.status == 'completed', Order.coin == c).scalar() or 0

        total_vnd_in_month = db.session.query(func.sum(Order.amount_vnd)).filter(Order.status == 'completed', Order.mode == 'buy', Order.created_at >= first_day_of_month).scalar() or 0
        total_vnd_out_month = db.session.query(func.sum(Order.amount_vnd)).filter(Order.status == 'completed', Order.mode == 'sell', Order.created_at >= first_day_of_month).scalar() or 0

        stats_dict = {
            "total_vnd_in": total_vnd_in, "total_vnd_out": total_vnd_out,
            "total_vnd_in_month": total_vnd_in_month, "total_vnd_out_month": total_vnd_out_month,
            **vols
        }
    except Exception as e:
        current_app.logger.error(f"Lỗi thống kê: {e}", exc_info=True)
        stats_dict = {}

    return jsonify({"success": True, "transactions": orders_list, "stats": stats_dict})

@bp.route("/api/admin/transactions/complete", methods=['POST'])
@admin_required
def complete_admin_transaction():
    data = request.json
    order = Order.query.filter_by(id=data.get('order_id')).first()
    if not order: return jsonify({"success": False, "message": "Không tìm thấy"}), 404
        
    order.status = 'completed'
    db.session.commit()

    try:
        action = "Đã nhận coin" if order.mode == 'buy' else "Đã nhận VNĐ"
        msg = f"✅ *ĐƠN HÀNG HOÀN TẤT*\nMã GD: *{order.id}*\nUser: *{order.username}*\nLoại: *{order.mode.upper()}*"
        send_telegram_notification(msg, order_id=order.id)
    except Exception as e: current_app.logger.error(f"Lỗi Telegram: {e}", exc_info=True)

    socketio.emit('order_completed', {'order_id': order.id}, room=order.id)
    return jsonify({"success": True, "message": f"Đã hoàn tất đơn hàng {order.id}"})

@bp.route("/api/public-transactions", methods=['GET'])
def get_public_transactions():
    try:
        recent_orders = Order.query.filter_by(status='completed').order_by(Order.created_at.desc()).limit(10).all()
        orders_list = [{
            "mode": "Mua" if o.mode == 'buy' else "Bán",
            "coin": o.coin.upper(),
            "amount_coin": round(o.amount_coin, 2), 
            "created_at": o.created_at.strftime("%d/%m/%Y %H:%M")
        } for o in recent_orders]
        return jsonify({"success": True, "transactions": orders_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route("/api/admin/transactions/history", methods=['GET'])
@admin_required
def get_admin_transactions_history():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    filter_username = request.args.get('username')
    filter_coin = request.args.get('coin')
    filter_date_from = request.args.get('date_from')
    filter_date_to = request.args.get('date_to')

    query = Order.query.filter_by(status='completed')

    if filter_username:
        search_term = f"%{filter_username}%"
        query = query.filter(or_(Order.username.ilike(search_term), Order.id.ilike(search_term)))
    if filter_coin and filter_coin != 'all':
        query = query.filter(Order.coin == filter_coin)
    if filter_date_from:
        try: query = query.filter(Order.created_at >= datetime.strptime(filter_date_from, '%Y-%m-%d'))
        except: pass
    if filter_date_to:
        try: query = query.filter(Order.created_at < (datetime.strptime(filter_date_to, '%Y-%m-%d') + timedelta(days=1)))
        except: pass

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    orders_list = [{
        "id": o.id, "mode": "Mua" if o.mode == 'buy' else "Bán",
        "coin": o.coin.upper(), "amount_vnd": o.amount_vnd, "amount_coin": o.amount_coin,
        "status": o.status, "created_at": o.created_at.strftime("%d/%m/%Y %H:%M"),
        "username": o.username
    } for o in pagination.items]

    return jsonify({
        "success": True, "transactions": orders_list,
        "pagination": {"total_pages": pagination.pages, "current_page": page, "total_items": pagination.total}
    })

@bp.route("/api/admin/users", methods=['GET'])
@admin_required
def get_admin_all_users():
    user = get_user_from_request()
    
    # Lấy tham số trang (mặc định trang 1, 20 người/trang)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Query cơ bản
    query = User.query.filter(User.username != user.username).order_by(User.id.asc())
    
    # Phân trang
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    users_list = [{
        "id": u.id, "username": u.username, "email": u.email, "role": u.role,
        "order_count": Order.query.filter_by(username=u.username).count()
    } for u in pagination.items] # Chỉ lấy items của trang hiện tại

    return jsonify({
        "success": True, 
        "users": users_list,
        "pagination": {
            "total_pages": pagination.pages,
            "current_page": page,
            "total_items": pagination.total
        }
    })

@bp.route("/api/user/my-transactions", methods=['GET'])
def get_user_transactions():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401

    page = request.args.get('page', 1, type=int)
    per_page = 10 

    query = Order.query.filter_by(username=user.username).order_by(Order.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    orders_list = []
    for order in pagination.items:
        status_vi = "Đã hoàn thành" if order.status == 'completed' else "Đang chờ xử lý" if order.status == 'pending' else "Đã hủy"
        orders_list.append({
            "id": order.id, "mode": "Mua" if order.mode == 'buy' else "Bán",
            "coin": order.coin.upper(), "amount_vnd": order.amount_vnd,
            "amount_coin": order.amount_coin, "status_vi": status_vi,
            "created_at": order.created_at.strftime("%d/%m/%Y %H:%M")
        })
        
    return jsonify({
        "success": True, 
        "transactions": orders_list,
        "pagination": {
            "total_pages": pagination.pages,
            "current_page": page
        }
    })

# --- ROUTES KYC ---

@bp.route("/api/user/submit-kyc", methods=['POST'])
def submit_kyc():
    user = get_user_from_request()
    if not user: return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    existing_kyc = KYC.query.filter_by(user_id=user.id).first()
    if existing_kyc and existing_kyc.status in ['pending', 'approved']:
        return jsonify({"success": False, "message": "Yêu cầu đang chờ hoặc đã duyệt."}), 400

    full_name = request.form.get('full_name')
    id_number = request.form.get('id_number')
    
    if 'id_front' not in request.files or 'id_back' not in request.files:
        return jsonify({"success": False, "message": "Thiếu ảnh!"}), 400

    files_map = {
        'id_front': request.files['id_front'], 'id_back': request.files['id_back'],
        'selfie': request.files['selfie'], 'paper': request.files['paper']
    }
    
    saved_filenames = {}
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    
    try:
        for key, f in files_map.items():
            if not is_valid_image(f) or not allowed_kyc_file(f.filename):
                return jsonify({"success": False, "message": f"Ảnh {key} lỗi hoặc không hợp lệ"}), 400
            
            fname = secure_filename(f"{user.username}_{ts}_{key}.jpg")
            f.save(os.path.join(current_app.config['KYC_UPLOAD_FOLDER'], fname))
            saved_filenames[key] = fname

        if existing_kyc:
            existing_kyc.full_name = full_name
            existing_kyc.id_number = id_number
            existing_kyc.id_front_image = saved_filenames['id_front']
            existing_kyc.id_back_image = saved_filenames['id_back']
            existing_kyc.selfie_image = saved_filenames['selfie']
            existing_kyc.paper_image = saved_filenames['paper']
            existing_kyc.status = 'pending'
            existing_kyc.submitted_at = datetime.now()
        else:
            new_kyc = KYC(
                user_id=user.id, full_name=full_name, id_number=id_number,
                id_front_image=saved_filenames['id_front'], id_back_image=saved_filenames['id_back'],
                selfie_image=saved_filenames['selfie'], paper_image=saved_filenames['paper'],
                status='pending'
            )
            db.session.add(new_kyc)
        
        db.session.commit()
        eventlet.spawn(send_telegram_notification, f"🛡️ *YÊU CẦU KYC MỚI*\nUser: {user.username}\nTên: {full_name}")
        return jsonify({"success": True, "message": "Gửi KYC thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route("/api/user/kyc-status", methods=['GET'])
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

@bp.route("/api/admin/kyc-list", methods=['GET'])
@admin_required
def admin_get_kyc_list():
    reqs = KYC.query.order_by(
        case((KYC.status == 'pending', 1), (KYC.status == 'approved', 2), else_=3),
        KYC.submitted_at.desc()
    ).all()
    
    result = [{
        "id": k.id, "username": k.user.username if k.user else "N/A",
        "full_name": k.full_name, "id_number": k.id_number, "status": k.status,
        "submitted_at": k.submitted_at.strftime("%d/%m/%Y"),
        "id_front": k.id_front_image, "id_back": k.id_back_image,
        "selfie": k.selfie_image, "paper": k.paper_image, "admin_note": k.admin_note
    } for k in reqs]
    return jsonify({"success": True, "requests": result})

@bp.route("/api/kyc-image/<path:filename>") 
def serve_kyc_image(filename):
    user = get_user_from_request()
    if not user:
        token = request.args.get('token')
        if token:
            try:
                payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
                user = User.query.filter_by(username=payload.get('username')).first()
            except: pass
    if not user or user.role != 'Admin': return "Forbidden", 403
    return send_from_directory(current_app.config['KYC_UPLOAD_FOLDER'], filename) 

@bp.route("/api/admin/kyc-review", methods=['POST'])
@admin_required
def admin_review_kyc():
    data = request.json
    kyc = KYC.query.get(data.get('kyc_id'))
    if not kyc: return jsonify({"success": False, "message": "Không tìm thấy"}), 404
    
    action = data.get('action')
    kyc.status = 'approved' if action == 'approve' else 'rejected'
    kyc.admin_note = data.get('note', '')
    kyc.reviewed_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True, "message": f"Đã {action} yêu cầu KYC."})

# --- ROUTES HTML (Frontend) ---

@bp.route('/')
def serve_index():
    settings = load_settings()
    if settings.get('maintenance_mode') == 'on':
        return render_template('maintenance.html')
    return render_template('index.html')

@bp.route('/<path:filename>')
def serve_html(filename):
    settings = load_settings()
    allowed_pages = ['login.html', 'admin_dashboard.html', 'admin_history.html', 'admin_users.html', 'admin_kyc.html', 'admin_spread.html', 'admin_settings.html', 'index.html']
    
    if filename.endswith('.html'):
        if settings.get('maintenance_mode') == 'on' and filename not in allowed_pages:
            return render_template('maintenance.html')
        return render_template(filename)
    return "Page not found", 404

# --- ROUTES Public API / Debug ---

@bp.route("/api/get-rate-buy-sell", methods=['GET'])
def api_get_rate_buy_sell():
    coin = request.args.get('coin', '').lower()
    if coin:
        rates = price_service.get_rate_buy_sell(coin)
        return jsonify(rates) if rates else (jsonify({"error": "Not found"}), 404)
    return jsonify({"success": True, "data": price_service.get_all_prices(), "timestamp": datetime.now().isoformat()})

@bp.route("/api/all-prices", methods=['GET'])
def api_all_prices():
    return jsonify(price_service.get_all_prices())

@bp.route("/api/start", methods=['GET'])
def api_start():
    return jsonify({
        "status": "online", "service": "Buser Price Service", "version": "2.0",
        "prices": price_service.get_all_prices()
    })

@bp.route("/api/usd-vnd-rate", methods=['GET'])
def api_usd_vnd_rate():
    rate = price_service.fetch_usd_vnd_rate()
    return jsonify({"success": True, "rate": rate})

@bp.route("/api/admin/update-spread", methods=['POST'])
@admin_required
def admin_update_spread():
    data = request.json
    coin = data.get('coin', '').lower()
    buy_percent = float(data.get('buy_percent', 1.5))
    sell_percent = float(data.get('sell_percent', 1.5))
    
    try:
        price_service.update_spread(coin, buy_percent, sell_percent)
        return jsonify({"success": True, "message": f"Đã cập nhật spread cho {coin}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route("/api/admin/get-spread", methods=['GET'])
@admin_required
def admin_get_spread():
    return jsonify({"success": True, "spread_config": price_service.spread_config})

@bp.route("/api/site-config", methods=['GET'])
def get_site_config():
    settings = load_settings()
    return jsonify({
        "success": True,
        "liquidity": {
            "usdt": settings.get('liquidity_usdt', 0), "btc": settings.get('liquidity_btc', 0),
            "eth": settings.get('liquidity_eth', 0), "bnb": settings.get('liquidity_bnb', 0),
            "sol": settings.get('liquidity_sol', 0)
        },
        "fee_table": settings.get('fee_html_content', '')
    })

@bp.route("/api/debug/crypto-price-usd", methods=['GET'])
def debug_crypto_price_usd():
    coin = request.args.get('coin', 'btc').lower()
    price = price_service.get_crypto_price_usd(coin)
    return jsonify({"coin": coin, "price_usd": price}) if price else (jsonify({"error": "Error"}), 500)

@bp.route("/api/debug/cache-status", methods=['GET'])
def debug_cache_status():
    with price_service.cache_lock:
        return jsonify(str(price_service.cache))

@bp.route("/api/health", methods=['GET'])
def health_check():
    try:
        db.session.execute('SELECT 1')
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- SOCKET EVENTS ---

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room_id')
    if room:
        from flask_socketio import join_room
        join_room(room)
        current_app.logger.error(f"✅ Client joined room: {room}", exc_info=True)

@socketio.on('connect')
def handle_connect():
    print("Socket Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Socket Client disconnected")

@bp.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    return jsonify({'csrf_token': generate_csrf()})