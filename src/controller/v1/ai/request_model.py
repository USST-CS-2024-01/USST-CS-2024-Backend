from typing import Optional, List

from pydantic import BaseModel, Field

from model.request_model import ListQueryRequest


class CreateDocumentEvaluationRequest(BaseModel):
    file_id: int = Field(..., title="文件ID")
