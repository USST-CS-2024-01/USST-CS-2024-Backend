from typing import List, Optional

from pydantic import Field

from model.response_model import BaseResponse
from model.schema import TaskSchema


class TaskChainResponse(BaseResponse):
    task_chain: List[TaskSchema] = Field(..., description="任务链")
    current_task_id: Optional[int] = Field(None, description="当前任务ID")
