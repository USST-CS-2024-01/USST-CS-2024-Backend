from typing import Optional
from model.enum import AccountStatus, UserType
from model.request_model import ListQueryRequest
from pydantic import BaseModel, Field


class CreateGroupRoleRequest(BaseModel):
    role_name: str = Field(..., description="角色名称", min_length=1, max_length=50)
    role_description: str = Field(
        ..., description="角色描述", min_length=1, max_length=1000
    )
    is_manager: bool = Field(False, description="是否为组长角色")
