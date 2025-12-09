import eventlet
eventlet.monkey_patch()
from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from extensions import db, socketio, mail, limiter, migrate, csrf
from models import User
from helpers import load_settings, clean_old_bills, update_price_task, create_system_admin
from routes import bp as main_bp

load_dotenv()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # 1. Cấu hình Logging (Ghi nhật ký lỗi)
    if not app.debug:
        if not os.path.exists('logs'): os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/buser.log', maxBytes=10240 * 1024, backupCount=10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    # 2. Cấu hình các Thư mục & Email
    app.config['UPLOAD_FOLDER'] = 'uploads/bills'
    app.config['KYC_UPLOAD_FOLDER'] = 'uploads/kyc'
    app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024
    
    # Cấu hình Mail từ .env
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

    # 3. Cấu hình Database & Bảo mật
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///buser.db')
    if database_url.startswith("postgres://"): 
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-change-me')

    # 4. Khởi tạo các công cụ (Extensions)
    db.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": allowed_origins}})

    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()         # Tạo bảng nếu chưa có
        load_settings()         # Load file config.json
        create_system_admin()   # Tự động tạo Admin từ .env

    return app

app = create_app()

# --- CHẠY SERVER ---
if __name__ == '__main__':
    try:
        scheduler = BackgroundScheduler()
        
        # Job 1: Cập nhật giá Coin (60 giây/lần)
        scheduler.add_job(func=update_price_task, trigger="interval", seconds=60)
        
        # Job 2: Dọn dẹp bill cũ (24 giờ/lần)
        # Lưu ý: Cần truyền biến 'app' vào để hàm này có thể truy cập Database
        scheduler.add_job(func=clean_old_bills, trigger="interval", hours=24, args=[app])
        
        scheduler.start()
        print(">>> ✅ Đã kích hoạt: Auto-Clean Bill & Auto-Update Prices")
    except Exception as e:
        print(f"❌ Lỗi khởi chạy Scheduler: {e}")

    print(">>> 🚀 SERVER STARTED tại http://127.0.0.1:5000 <<<")
    
    socketio.run(app, debug=False, port=5000, allow_unsafe_werkzeug=False)