from typing import Optional
from model.enum import AccountStatus, UserType
from model.request_model import ListQueryRequest
from pydantic import BaseModel, Field


class ListUserRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|username|email|user_type|account_status|employee_id|name)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    user_type: Optional[UserType] = Field(None, description="用户类型")
    account_status: Optional[AccountStatus] = Field(None, description="账户状态")


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(
        None, description="用户名", pattern=r"^[a-zA-Z0-9_]{4,20}$"
    )
    email: Optional[str] = Field(
        None,
        description="邮箱",
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    user_type: Optional[UserType] = Field(
        None, description="用户类型", pattern=r"^(admin|teacher|student)$"
    )
    account_status: Optional[AccountStatus] = Field(
        None, description="账户状态", pattern=r"^(active|inactive)$"
    )
    employee_id: Optional[str] = Field(
        None, description="员工编号", pattern=r"^[a-zA-Z0-9]{4,20}$"
    )
    name: Optional[str] = Field(None, description="姓名")
    # 密码6-20位，可包含数字、字母和特殊字符
    password: Optional[str] = Field(
        None,
        description="密码",
        pattern=r"^[a-zA-Z0-9~!@#$%^&*()_+`\-={}|\[\]\\:\";'<>?,./]{6,20}$",
    )


class MeUserUpdateRequest(BaseModel):
    email: Optional[str] = Field(
        None,
        description="邮箱",
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    password: Optional[str] = Field(
        None,
        description="密码",
        pattern=r"^[a-zA-Z0-9~!@#$%^&*()_+`\-={}|\[\]\\:\";'<>?,./]{6,20}$",
    )
