from typing import Optional
from pydantic import BaseModel, Field

from model.response_model import BaseResponse
from model.schema import UserSchema


class ClassReturnItem(BaseModel):
    id: int = Field(..., description="班级ID")
    name: str = Field(..., description="班级名称")
    description: str = Field("", description="班级描述")
    status: str = Field(..., description="班级状态")
    stu_count: int = Field(..., description="学生数量")
    tea_list: list[UserSchema] = Field(..., description="教师列表")
    stu_list: Optional[list[UserSchema]] = Field(None, description="学生列表")