from typing import Optional

from pydantic import BaseModel, Field

from model.request_model import ListQueryRequest


class ListRepoRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|status|create_time|stat_time)$",
    )
    status: Optional[str] = Field(
        None, description="关键字", pattern=r"^(pending|completed|failed)$"
    )


class CreateRepoRequest(BaseModel):
    repo_url: str = Field(..., description="仓库地址")
