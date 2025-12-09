from extensions import db  
from datetime import datetime
import secrets
import json 


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
