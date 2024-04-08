from typing import Optional
from model.enum import AccountStatus, UserType
from model.request_model import ListQueryRequest
from pydantic import Field


class ListUserRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|username|email|user_type|account_status|employee_id|name)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    user_type: Optional[UserType] = Field(None, description="用户类型")
    account_status: Optional[AccountStatus] = Field(None, description="账户状态")
