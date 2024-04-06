from sanic import Blueprint, json, log
from sqlalchemy import select

from model import User
from util.sql_model import to_dict

bp = Blueprint("user", url_prefix="/user")


@bp.route("/list", methods=["GET"])
async def list_users(request):
    stmt = select(User)
    db = request.app.ctx.db
    log.logger.info("Querying users...")
    users = db().scalars(stmt)
    return json({"users": [to_dict(user) for user in users]})
