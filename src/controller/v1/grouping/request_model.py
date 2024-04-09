from typing import Optional

from pydantic import BaseModel, Field


class CreateGroupingRequest(BaseModel):
    name: str = Field(..., description="分组名称", min_length=1, max_length=50)
    leader: Optional[int] = Field(None, description="组长ID")
