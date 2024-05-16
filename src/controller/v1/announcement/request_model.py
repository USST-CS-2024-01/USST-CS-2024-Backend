from typing import Optional, List

from pydantic import BaseModel, Field

from model.request_model import ListQueryRequest


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(..., description="标题", min_length=1, max_length=100)
    content: str = Field(..., description="内容", min_length=1, max_length=10000)
    receiver_type: str = Field(
        ...,
        description="接收者类型",
        pattern=r"^(all|class|group|individual)$",
    )
    receiver_id: Optional[int] = Field(None, description="接收者ID")
    receiver_role: Optional[str] = Field(
        None, description="接收者角色", pattern=r"^(teacher|student|admin)$"
    )
    attachments: Optional[List[int]] = Field(None, description="附件ID列表")


class ListAnnouncementRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|publish_time)$",
    )
    status: Optional[str] = Field(
        None,
        description="状态",
        pattern=r"^(all|read|unread)$",
    )
    class_id: Optional[int] = Field(None, description="班级ID")


class UpdateAnnouncementRequest(BaseModel):
    title: Optional[str] = Field(None, description="标题", min_length=1, max_length=100)
    content: Optional[str] = Field(
        None, description="内容", min_length=1, max_length=10000
    )
    attachments: Optional[List[int]] = Field(None, description="附件ID列表")
