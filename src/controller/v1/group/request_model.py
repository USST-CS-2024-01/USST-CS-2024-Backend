from typing import Optional, List

from pydantic import BaseModel, Field


class CreateGroupRequest(BaseModel):
    name: str = Field(..., description="分组名称", min_length=1, max_length=50)
    leader: Optional[int] = Field(None, description="组长ID")


class UpdateGroupMemberRequest(BaseModel):
    repo_usernames: List[str] = Field(None, description="成员使用的Git代码仓库用户名列表")
    role_list: List[int] = Field(
        None, description="设定的用户角色ID，每个角色在一组中应当不出现重复，同时，组长角色无法手动设定给他人，无法解除"
    )
