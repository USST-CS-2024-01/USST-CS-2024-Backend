from sanic import Blueprint, json

from controller.v1.user.response_model import MeUserResponse
from middleware.auth import need_login
from model.schema import UserSchema

user_bp = Blueprint("user", url_prefix="/user")


@user_bp.route("/me", methods=["GET"])
@need_login()
async def get_user_info(request):
    return MeUserResponse(user=UserSchema.from_orm(request.ctx.user)).json_response()
