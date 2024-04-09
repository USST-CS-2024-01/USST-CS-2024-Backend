from pydantic import Field

from model.response_model import BaseResponse
from model.schema import UserSchema


class MeUserResponse(BaseResponse):
    """
    查询当前用户响应
    """

    data: UserSchema = Field(..., description="用户信息")
