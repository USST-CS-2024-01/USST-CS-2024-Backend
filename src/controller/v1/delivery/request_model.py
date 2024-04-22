from typing import Optional

from pydantic import BaseModel, Field


class CreateDeliveryRequest(BaseModel):
    delivery_comments: Optional[str] = Field(
        None, description="交付物备注", min_length=0, max_length=1000
    )


class AddDeliveryItemRequest(BaseModel):
    item_type: str = Field(..., description="交付物类型", pattern="^(file|repo)$")
    item_id: int = Field(..., description="交付物ID")
