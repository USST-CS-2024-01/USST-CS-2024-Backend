from typing import Optional, Dict, List

from pydantic import BaseModel, Field

from model.request_model import ListQueryRequest


class ListClassRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|name|status)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    status: Optional[str] = Field(
        None,
        description="状态",
        pattern=r"^(not_started|grouping|teaching|finished)$",
    )
    user_id: Optional[int] = Field(None, description="用户ID，用于查询用户所在班级")


class ChangeClassInfoRequest(BaseModel):
    name: str = Field(..., description="班级名称", min_length=1, max_length=50)
    description: Optional[str] = Field(
        None, description="班级描述", min_length=1, max_length=1000
    )


class AddClassMemberRequest(BaseModel):
    user_dict: Dict[str, bool] = Field(
        ..., description="用户ID列表，key 为用户ID，value 为是否为教师"
    )


class RemoveClassMemberRequest(BaseModel):
    user_id_list: List[int] = Field(..., description="用户ID")


class CreateClassRequest(BaseModel):
    name: str = Field(..., description="班级名称", min_length=1, max_length=50)
    description: str = Field(..., description="班级描述", min_length=1, max_length=1000)
