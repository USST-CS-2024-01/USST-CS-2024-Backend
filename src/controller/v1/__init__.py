from sanic import Blueprint

from .ai import ai_bp
from .announcement import announcement_bp
from .auth import auth_bp
from .class_ import class_bp
from .delivery import delivery_bp
from .file import file_bp
from .group import group_bp
from .group_meeting import group_meeting_bp
from .group_member_score import group_member_score_bp
from .group_task import group_task_bp
from .repo_record import repo_record_bp
from .role import role_bp
from .task import task_bp
from .user import user_bp
from .score import score_bp
from .config import config_bp
from .log import log_bp

bp = Blueprint.group(
    user_bp,
    auth_bp,
    class_bp,
    task_bp,
    role_bp,
    group_bp,
    file_bp,
    group_task_bp,
    group_meeting_bp,
    group_member_score_bp,
    announcement_bp,
    delivery_bp,
    repo_record_bp,
    ai_bp,
    score_bp,
    config_bp,
    log_bp,
    url_prefix="/v1",
)
