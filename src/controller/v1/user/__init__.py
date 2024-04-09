from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import func, select, or_
from controller.v1.user.request_model import (
    ListUserRequest,
    MeUserUpdateRequest,
    UserUpdateRequest,
)
from controller.v1.user.response_model import MeUserResponse
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import User
from model.enum import UserType
from model.response_model import BaseListResponse, BaseResponse, ErrorResponse
from model.schema import UserSchema
from util.parameter import generate_parameters_from_pydantic
from util import encrypt
from service import user as user_service

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
        code=200, message="ok", data=UserSchema.from_orm(request.ctx.user)
    ).json_response()


@user_bp.route("/list", methods=["GET"])
@openapi.summary("查询用户列表")
@openapi.tag("用户接口")
@openapi.definition(parameter=generate_parameters_from_pydantic(ListUserRequest))
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
            # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
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


@user_bp.route("/me", methods=["PUT"])
@openapi.summary("修改当前用户信息")
@openapi.tag("用户接口")
@openapi.description("""修改当前用户信息，只能修改邮箱和密码，该接口所有用户均可访问""")
@openapi.body(
    {
        "application/json": MeUserUpdateRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
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
@validate(json=MeUserUpdateRequest)
async def update_user_info(request, body: MeUserUpdateRequest):
    db = request.app.ctx.db

    user = request.ctx.user

    update_dict = body.dict(exclude_unset=True)
    if not update_dict:
        return ErrorResponse.new_error(code=400, message="Nothing to update")

    # 如果修改了密码，需要重新加密
    if "password" in update_dict:
        update_dict["password_hash"] = encrypt.bcrypt_hash(update_dict["password"])
        update_dict.pop("password")

    stmt = User.__table__.update().where(User.id == user.id).values(update_dict)

    with db() as sess:
        sess.execute(stmt)
        sess.commit()

    return MeUserResponse(
        code=200,
        message="ok",
        data=UserSchema.from_orm(user_service.get_user(db, user_id=user.id)),
    ).json_response()


@user_bp.route("/<user_id:int>", methods=["GET"])
@openapi.summary("查询用户信息")
@openapi.tag("用户接口")
@openapi.parameter(name="user_id", description="用户ID", in_="path", required=True)
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
@need_role([UserType.admin])
async def get_user(request, user_id):
    db = request.app.ctx.db

    user = user_service.get_user(db, user_id=user_id)

    if not user:
        return ErrorResponse.new_error(code=404, message="用户不存在")

    return MeUserResponse(
        code=200, message="ok", data=UserSchema.from_orm(user)
    ).json_response()


@user_bp.route("/<user_id:int>", methods=["DELETE"])
@openapi.summary("删除用户")
@openapi.tag("用户接口")
@openapi.parameter(name="user_id", description="用户ID", in_="path", required=True)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin])
async def delete_user(request, user_id):
    db = request.app.ctx.db

    user = user_service.get_user(db, user_id=user_id)

    if not user:
        return ErrorResponse.new_error(code=404, message="用户不存在")
    if user.id == request.ctx.user.id:
        return ErrorResponse.new_error(code=400, message="不能删除自己")
    if user.id == 1:
        return ErrorResponse.new_error(code=400, message="不能删除超级管理员")

    stmt = User.__table__.delete().where(User.id == user_id)

    with db() as sess:
        sess.execute(stmt)
        sess.commit()

    return BaseResponse(code=200, message="ok").json_response()


@user_bp.route("/<user_id:int>", methods=["PUT"])
@openapi.summary("修改用户信息")
@openapi.tag("用户接口")
@openapi.parameter(name="user_id", description="用户ID", in_="path", required=True)
@openapi.body(
    {
        "application/json": UserUpdateRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
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
@need_role([UserType.admin])
@validate(json=UserUpdateRequest)
async def update_user(request, user_id, body: UserUpdateRequest):
    db = request.app.ctx.db

    user = user_service.get_user(db, user_id=user_id)
    if not user:
        return ErrorResponse.new_error(code=404, message="用户不存在")

    update_dict = body.dict(exclude_unset=True)

    # 禁止修改自己和超级管理员的用户类型
    if user.id == request.ctx.user.id or user.id == 1:
        if "user_type" in update_dict:
            update_dict.pop("user_type")

    # 如果修改了密码，需要重新加密
    if "password" in update_dict:
        # 禁止修改超级管理员的密码
        if user.id == 1 and user.id != request.ctx.user.id:
            return ErrorResponse.new_error(code=400, message="不能修改超级管理员密码")
        update_dict["password_hash"] = encrypt.bcrypt_hash(update_dict["password"])
        update_dict.pop("password")

    stmt = User.__table__.update().where(User.id == user_id).values(update_dict)

    with db() as sess:
        sess.execute(stmt)
        sess.commit()

    return MeUserResponse(
        code=200,
        message="ok",
        data=UserSchema.from_orm(user_service.get_user(db, user_id=user_id)),
    ).json_response()


@user_bp.route("/create", methods=["POST"])
@openapi.summary("创建用户")
@openapi.tag("用户接口")
@openapi.body(
    {
        "application/json": UserUpdateRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
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
@need_role([UserType.admin])
@validate(json=UserUpdateRequest)
async def create_user(request, body: UserUpdateRequest):
    db = request.app.ctx.db

    # 所有的参数必须都不为空
    if not all(body.dict().values()):
        return ErrorResponse.new_error(code=400, message="All fields are required")

    has_dup_stmt = (
        select(func.count())
        .where(
            or_(
                User.username == body.username,
                User.email == body.email,
                User.employee_id == body.employee_id,
            )
        )
        .limit(1)
    )
    with db() as sess:
        has_dup = sess.execute(has_dup_stmt).scalar()
    if has_dup:
        return ErrorResponse.new_error(
            code=409, message="Username, email or employee_id already exists"
        )

    insert_dict = body.dict()
    insert_dict["password_hash"] = encrypt.bcrypt_hash(insert_dict["password"])
    insert_dict.pop("password")

    # 创建一个新的 User 对象
    new_user = User(**insert_dict)
    new_user_pydantic: UserSchema
    with db() as sess:
        # 添加到会话并提交，这将自动填充 new_user 的 id 属性
        sess.add(new_user)
        sess.commit()
        # 刷新对象，以获取数据库中的所有字段
        sess.refresh(new_user)
        new_user_pydantic = UserSchema.from_orm(new_user)

    return MeUserResponse(
        code=200,
        message="ok",
        data=new_user_pydantic,
    ).json_response()
