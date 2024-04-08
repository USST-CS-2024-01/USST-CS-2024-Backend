from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # key_exchange:<uuid>
    session_id: str = Field(
        ...,
        description="登录初始化会话ID，需要在初始化登录请求中获取",
        examples=["key_exchange:123e4567-e89b-12d3-a456-426614174000"],
        pattern=r"^key_exchange:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    )
    username: str = Field(
        ...,
        description="用户名",
        examples=["username"],
        min_length=1,
        max_length=32,
    )
    # Base64 encoded
    password: str = Field(
        ...,
        description="密码，由客户端使用AES密钥加密后进行Base64编码",
        examples=["MTE0NTE0MTkxOTgxMAo="],
        min_length=1,
        max_length=1024,
        pattern=r"^[A-Za-z0-9+/=]{1,}$",
    )
