from pydantic import BaseModel, Field


class UpdateConfigRequestModel(BaseModel):
    value: str = Field(..., description="配置值", min_length=1, max_length=100000)
