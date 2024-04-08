from typing import Optional

from pydantic import BaseModel, Field
from sanic import HTTPResponse
from sanic.response import JSONResponse


class BaseResponse(BaseModel):
    """
    基础响应
    """

    code: int = Field(200, description="状态码")
    message: str = Field("ok", description="消息")

    def json_response(self) -> HTTPResponse:
        """
        返回 JSON 响应
        :return: JSON 响应
        """
        resp = HTTPResponse(
            body=self.json(),
            content_type="application/json",
            status=self.code,
        )
        return resp


class ErrorResponse(BaseResponse):
    """
    错误响应
    """

    code: int = Field(400, description="状态码")
    message: str = Field("error", description="消息")
    detail: Optional[str] = Field(None, description="详细信息")

    @staticmethod
    def new_error(code: int, message: str, detail: str = None) -> JSONResponse:
        """
        创建错误响应
        :param code:     状态码
        :param message:  消息
        :param detail:   详细信息
        :return:         错误响应
        """
        err_resp = ErrorResponse(code=code, message=message, detail=detail)

        return JSONResponse(err_resp.dict(), status=code)