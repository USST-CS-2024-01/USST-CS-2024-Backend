from typing import Optional

from pydantic import BaseModel, Field

from model.response_model import BaseResponse
from model.schema import UserSchema


class ClassReturnItem(BaseModel):
    id: int = Field(..., description="班级ID")
    name: str = Field(..., description="班级名称")
    description: str = Field("", description="班级描述")
    status: str = Field(..., description="班级状态")
    stu_count: Optional[int] = Field(None, description="学生数量")
    tea_count: Optional[int] = Field(None, description="教师数量")
    first_task_id: Optional[int] = Field(None, description="第一个任务ID")
    tea_list: Optional[list[UserSchema]] = Field(None, description="教师列表")
    stu_list: Optional[list[UserSchema]] = Field(None, description="学生列表")


class ClassMemberOperationResult(BaseResponse):
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_list: list[UserSchema] = Field([], description="失败列表")
