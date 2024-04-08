from typing import List, Optional, TypeVar

from pydantic import BaseModel, Field
from sanic import HTTPResponse
from sanic.response import JSONResponse


class ListQueryRequest(BaseModel):
    """
    列表查询请求
    """

    page: Optional[int] = Field(1, description="页码", ge=1)
    page_size: Optional[int] = Field(10, description="每页数量", ge=1, le=100)
    order_by: Optional[str] = Field(None, description="排序字段")
    asc: Optional[bool] = Field(True, description="是否升序")

    @property
    def offset(self):
        if self.page is None or self.page_size is None:
            return 0
        return (self.page - 1) * self.page_size

    @property
    def limit(self):
        return self.page_size or 10
