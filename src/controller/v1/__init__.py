from sanic import Blueprint

from .user import bp as user_bp

bp = Blueprint.group(user_bp, url_prefix="/v1")
