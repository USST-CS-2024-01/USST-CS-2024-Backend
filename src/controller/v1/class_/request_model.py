from typing import Optional
from model.enum import AccountStatus, UserType
from model.request_model import ListQueryRequest
from pydantic import BaseModel, Field


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
