from pydantic import Field

from model.response_model import BaseResponse


class LoginInitResponse(BaseResponse):
    """
    登录初始化响应
    """

    session_id: str = Field(..., description="会话ID，须在登录请求中携带")
    expires_in: int = Field(..., description="有效时间（秒）")
    key: str = Field(..., description="AES密钥，Hex编码")
    iv: str = Field(..., description="AES IV，Hex编码")


class LoginResponse(BaseResponse):
    """
    登录成功响应
    """

    session_id: str = Field(..., description="会话ID，用于后续请求")
    user: dict = Field(..., description="用户信息")
