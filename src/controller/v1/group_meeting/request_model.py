from typing import Optional

from pydantic import Field, BaseModel

from model.request_model import ListQueryRequest


class ListGroupMeetingRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|start_time|end_time|meeting_type|task_id)$",
    )
    task_id: Optional[int] = Field(None, description="任务ID")
    kw: Optional[str] = Field(None, description="关键字")


class CreateGroupMeetingRequest(BaseModel):
    name: str = Field(..., description="会议名称", min_length=1, max_length=50)
    start_time: int = Field(..., description="开始时间")
    end_time: int = Field(..., description="结束时间")
    meeting_type: Optional[str] = Field("document_only", description="会议类型")
    meeting_link: Optional[str] = Field(None, description="会议链接")
    related_files: list[int] = Field([], description="相关文件ID列表")


class UpdateGroupMeetingRequest(BaseModel):
    name: Optional[str] = Field(
        None, description="会议名称", min_length=1, max_length=50
    )
    start_time: Optional[int] = Field(None, description="开始时间")
    end_time: Optional[int] = Field(None, description="结束时间")
    meeting_type: Optional[str] = Field(None, description="会议类型")
    meeting_link: Optional[str] = Field(None, description="会议链接")
    related_files: Optional[list[int]] = Field([], description="相关文件ID列表")
