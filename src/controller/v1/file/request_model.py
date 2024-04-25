from typing import Optional

from pydantic import BaseModel, Field

from model import FileOwnerType
from model.request_model import ListQueryRequest


class CreateFileRequest(BaseModel):
    file_name: str = Field(..., description="文件名称，最大长度为500", max_length=500)
    owner_type: Optional[FileOwnerType] = Field(
        FileOwnerType.user, description="文件拥有者类型，默认为用户"
    )
    owner_id: Optional[int] = Field(None, description="文件拥有者ID")


class UpdateFileRequest(BaseModel):
    file_name: Optional[str] = Field(None, description="文件名称，最大长度为500", max_length=500)


class GetFileListRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|name|file_type|file_size|create_date|modify|date)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    user_id: Optional[int] = Field(None, description="用户ID")
    class_id: Optional[int] = Field(None, description="班级ID")
    group_id: Optional[int] = Field(None, description="小组ID")
