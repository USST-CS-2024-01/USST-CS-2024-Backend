from sanic import Blueprint

from .auth import auth_bp
from .user import user_bp

bp = Blueprint.group(user_bp, auth_bp, url_prefix="/v1")
