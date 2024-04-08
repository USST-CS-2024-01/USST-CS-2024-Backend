from tkinter import N
from turtle import st
from sanic import Blueprint, json
from sanic_ext import openapi
from sqlalchemy import func, select, or_
from controller.v1.user.request_model import ListUserRequest
from controller.v1.user.response_model import MeUserResponse
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import User
from model.enum import UserType
from model.response_model import BaseListResponse
from model.schema import UserSchema
from util.parameter import generate_parameters_from_pydantic

user_bp = Blueprint("user", url_prefix="/user")


@user_bp.route("/me", methods=["GET"])
@openapi.summary("查询当前用户信息")
@openapi.tag("用户接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": MeUserResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_user_info(request):
    return MeUserResponse(
        code=200, message="ok", user=UserSchema.from_orm(request.ctx.user)
    ).json_response()


@user_bp.route("/list", methods=["GET"])
@openapi.summary("查询用户列表")
@openapi.tag("用户接口")
@openapi.definition(
    parameter=generate_parameters_from_pydantic(ListUserRequest)
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin])
@validate(query=ListUserRequest)
async def get_user_list(request, query: ListUserRequest):
    db = request.app.ctx.db

    stmt = select(User)
    if query.kw:
        stmt = stmt.where(
            or_(
                User.username.like(f"%{query.kw}%"),
                User.email.like(f"%{query.kw}%"),
                User.employee_id.like(f"%{query.kw}%"),
                User.name.like(f"%{query.kw}%"),
            )
        )
    if query.order_by:
        stmt = stmt.order_by(
            getattr(getattr(User, query.order_by), query.asc and "asc" or "desc")()
        )
    stmt = stmt.offset(query.offset).limit(query.limit)
    count_stmt = select(func.count()).select_from(stmt.subquery())

    with db() as sess:
        users = sess.execute(stmt).scalars().all()
        total = sess.execute(count_stmt).scalar()

    user_list = [UserSchema.from_orm(user) for user in users]

    return BaseListResponse(
        code=200,
        message="ok",
        data=user_list,
        page=query.page,
        page_size=query.page_size,
        total=total,
    ).json_response()
