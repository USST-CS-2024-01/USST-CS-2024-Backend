from typing import Optional

from pydantic import Field, BaseModel

from model.request_model import ListQueryRequest


class ListGroupTaskRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|status|publish_time|deadline|update_time|priority)$",
    )
    status: Optional[str] = Field(
        None,
        description="状态",
        pattern=r"^(pending|normal|finished)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    priority: Optional[int] = Field(None, description="优先级")


class AddGroupTaskRequest(BaseModel):
    name: str = Field(..., description="任务名称", min_length=1, max_length=50)
    details: str = Field(
        ..., description="任务详情，Markdown格式", min_length=1, max_length=1000
    )
    assignees: list[int] = Field(..., description="分组角色ID列表")
    deadline: Optional[int] = Field(None, description="截止时间")
    priority: int = Field(..., description="优先级", ge=-10, le=100)
    related_files: list[int] = Field([], description="相关文件ID列表")


class UpdateGroupTaskRequest(BaseModel):
    name: Optional[str] = Field(None, description="任务名称", min_length=1, max_length=50)
    details: Optional[str] = Field(
        None, description="任务详情，Markdown格式", min_length=1, max_length=1000
    )
    assignees: Optional[list[int]] = Field(None, description="分组角色ID列表")
    deadline: Optional[int] = Field(None, description="截止时间")
    priority: Optional[int] = Field(None, description="优先级", ge=-10, le=100)
    related_files: Optional[list[int]] = Field([], description="相关文件ID列表")
    status: Optional[str] = Field(
        None,
        description="状态",
        pattern=r"^(pending|normal|finished)$",
    )
