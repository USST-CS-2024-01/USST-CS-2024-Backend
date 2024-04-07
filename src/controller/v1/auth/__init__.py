import base64
import time
import uuid

from sanic import Blueprint

from util.sql_model import to_dict
from middleware.validator import validate
from sanic_ext.extensions.openapi import openapi
from sqlalchemy import select

from controller.v1.auth.request_model import LoginRequest
from controller.v1.auth.response_model import LoginInitResponse, LoginResponse
from model import User, AccountStatus
from model.response_model import ErrorResponse
from util import encrypt

auth_bp = Blueprint("auth", url_prefix="/auth")


def generate_key_exchange_session_id() -> str:
    """
    Generate a key exchange session ID
    :return: Key exchange session ID
    """
    prefix = "key_exchange:"
    uuid_str = str(uuid.uuid4())
    return f"{prefix}{uuid_str}"


def generate_login_session_id() -> str:
    """
    Generate a login session ID
    :return: Login session ID
    """
    prefix = "login_session:"
    uuid_str = str(uuid.uuid4())
    timestamp = int(time.time())
    return f"{prefix}{uuid_str}-{timestamp}"


@auth_bp.route("/init", methods=["POST"])
@openapi.summary("初始化登录请求")
@openapi.tag("鉴权接口")
@openapi.description(
    """初始化登录请求，获取服务端提供的一次性AES密钥和IV。
加密模式为AES-128-CBC，密钥和IV均为16字节，使用PKCS7填充，过期时间为5分钟。"""
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": LoginInitResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
async def init(request):
    cache = request.app.ctx.cache
    session_id = generate_key_exchange_session_id()

    key, iv = encrypt.generate_key_iv()
    await cache.set_pickle(session_id, (key, iv), expire=300)

    resp = LoginInitResponse(
        session_id=session_id,
        expires_in=300,
        key=key.hex(),
        iv=iv.hex(),
    )

    return resp.json_response()


@auth_bp.route("/login", methods=["POST"])
@openapi.summary("登录")
@openapi.tag("鉴权接口")
@openapi.description(
    """登录接口，使用AES密钥加密密码后进行Base64编码。
需要先在`/auth/init`接口中获取AES密钥和IV，并在登陆时传递`session_id`。"""
)
@openapi.body(
    {
        "application/json": LoginRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@validate(json=LoginRequest)
async def login(request, body: LoginRequest):
    ctx = request.app.ctx

    db = ctx.db
    cache = ctx.cache

    try:
        key, iv = await cache.get_pickle(body.session_id)
        assert key and iv
        await cache.delete(body.session_id)
    except Exception as e:
        return ErrorResponse.new_error(
            403,
            "Invalid session",
            detail=str(e),
        )

    try:
        password_b64_decoded = base64.b64decode(body.password)
        password = encrypt.decrypt_aes(
            key,
            iv,
            password_b64_decoded,
        ).decode("utf-8")
    except Exception as e:
        return ErrorResponse.new_error(
            400,
            "Invalid username or password1",
            detail=str(e),
        )

    stmt = select(User).where(User.username == body.username).limit(1)
    with db() as db:
        user: User or None = db.scalar(stmt)

    if not user:
        return ErrorResponse.new_error(
            400,
            "Invalid username or password",
        )

    if not encrypt.bcrypt_compare(password, user.password_hash):
        return ErrorResponse.new_error(
            400,
            "Invalid username or password",
        )

    if user.account_status != AccountStatus.active:
        return ErrorResponse.new_error(
            403,
            "Account is not active",
        )

    login_session_id = generate_login_session_id()
    await cache.set_pickle(login_session_id, user, expire=3600)

    resp = LoginResponse(
        session_id=login_session_id,
        user=to_dict(user),
    )

    return resp.json_response()
