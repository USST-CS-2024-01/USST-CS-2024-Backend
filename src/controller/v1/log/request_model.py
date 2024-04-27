from typing import Optional

from pydantic import Field, BaseModel

from model.request_model import ListQueryRequest


class ListLogRequest(ListQueryRequest):
    order_by: Optional[str] = Field(
        None,
        description="排序字段",
        pattern=r"^(id|log_type|user_id|user_name|user_employee_id|user_type|operation_time|operation_ip)$",
    )
    kw: Optional[str] = Field(None, description="关键字")
    log_type: Optional[str] = Field(
        None,
        description="日志类型",
        min_length=1,
        max_length=50,
    )
    user_id: Optional[int] = Field(None, description="用户ID")
    user_name: Optional[str] = Field(None, description="用户名")
    user_employee_id: Optional[str] = Field(None, description="员工编号")
    user_type: Optional[str] = Field(
        None, description="用户类型", pattern=r"^(admin|teacher|student)$"
    )
    operation_time_start: Optional[int] = Field(
        None, description="操作时间开始时间戳", ge=1
    )
    operation_time_end: Optional[int] = Field(
        None, description="操作时间结束时间戳", ge=1
    )
    operation_ip: Optional[str] = Field(None, description="操作IP")
