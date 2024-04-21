from pydantic import Field, BaseModel


class CreateGroupMemberScoreRequest(BaseModel):
    score_map: dict[int, int] = Field(..., description="成员互评分数映射")
