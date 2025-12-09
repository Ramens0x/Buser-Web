from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')
mail = Mail()
limiter = Limiter(key_func=get_remote_address)
migrate = Migrate()
csrf = CSRFProtect()