from typing import Optional, List
from model.enum import AccountStatus, UserType
from model.request_model import ListQueryRequest
from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    name: str = Field(..., description="任务名称", max_length=500, min_length=1)
    content: str = Field(
        ..., description="任务简介（支持Markdown格式）", max_length=10000, min_length=1
    )
    specified_role: int = Field(..., description="指定任务提交时的角色ID")
    publish_time: int = Field(..., description="任务发布时间，时间戳")
    deadline: int = Field(..., description="任务截止时间，时间戳")
    grade_percentage: float = Field(
        ..., description="该部分任务占总分比重，所有任务比重之和不建议超过100%"
    )
    attached_files: Optional[List] = Field(
        None, description="任务相关附件列表，填写文件ID，文件需要是Class类型"
    )


class UpdateTaskRequest(BaseModel):
    name: Optional[str] = Field(
        None, description="任务名称", max_length=500, min_length=1
    )
    content: Optional[str] = Field(
        None, description="任务简介（支持Markdown格式）", max_length=10000, min_length=1
    )
    specified_role: Optional[int] = Field(None, description="指定任务提交时的角色ID")
    publish_time: Optional[int] = Field(None, description="任务发布时间，时间戳")
    deadline: Optional[int] = Field(None, description="任务截止时间，时间戳")
    grade_percentage: Optional[float] = Field(
        None, description="该部分任务占总分比重，所有任务比重之和不建议超过100%"
    )
    attached_files: Optional[List] = Field(
        None, description="任务相关附件列表，填写文件ID，文件需要是Class类型"
    )


class SetTaskSequenceRequest(BaseModel):
    sequences: List[int] = Field(
        ...,
        description="所有任务的完整排序，需要将所有该班级的任务都列入进去，且不能重复",
    )
