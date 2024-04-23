from typing import Optional

from pydantic import BaseModel, Field


class CreateDeliveryRequest(BaseModel):
    delivery_comments: Optional[str] = Field(
        None, description="交付物备注", min_length=0, max_length=1000
    )


class AddDeliveryItemRequest(BaseModel):
    item_type: str = Field(..., description="交付物类型", pattern="^(file|repo)$")
    item_id: int = Field(..., description="交付物ID")


class AcceptDeliveryRequest(BaseModel):
    score: Optional[int] = Field(None, description="分数", ge=0, le=100)


class RejectDeliveryRequest(BaseModel):
    delivery_comments: str = Field(
        ..., description="拒绝原因", min_length=1, max_length=1000
    )


class ScoreDetailRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")
    score: int = Field(..., description="分数", ge=0, le=100)
    score_details: Optional[dict] = Field(None, description="评语")
