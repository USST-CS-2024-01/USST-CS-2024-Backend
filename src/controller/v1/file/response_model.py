from pydantic import Field

from model.response_model import BaseResponse


class UploadSessionResponse(BaseResponse):
    session_id: str = Field(..., description="上传会话ID")
    upload_url: str = Field(..., description="上传URL")
