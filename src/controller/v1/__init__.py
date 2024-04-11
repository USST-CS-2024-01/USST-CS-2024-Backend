from sanic import Blueprint

from .auth import auth_bp
from .class_ import class_bp
from .group import group_bp
from .role import role_bp
from .task import task_bp
from .user import user_bp

bp = Blueprint.group(
    user_bp, auth_bp, class_bp, task_bp, role_bp, group_bp, url_prefix="/v1"
)
