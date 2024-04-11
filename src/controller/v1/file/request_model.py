from typing import Optional

from pydantic import BaseModel, Field

from model import FileOwnerType


class CreateFileRequest(BaseModel):
    file_name: str = Field(..., description="文件名称，最大长度为500", max_length=500)
    owner_type: Optional[FileOwnerType] = Field(
        FileOwnerType.user, description="文件拥有者类型，默认为用户"
    )
    owner_id: Optional[int] = Field(None, description="文件拥有者ID")
