from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select, func, or_
from controller.v1.log.request_model import ListLogRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import UserType, Log
from model.response_model import (
    BaseListResponse,
)
from model.schema import LogSchema
from util.parameter import generate_parameters_from_pydantic
from util.string import timestamp_to_datetime

log_bp = Blueprint("log", url_prefix="/log")


@log_bp.route("/list", methods=["GET"])
@openapi.summary("获取日志列表")
@openapi.tag("日志接口")
@openapi.definition(parameter=generate_parameters_from_pydantic(ListLogRequest))
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[LogSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin])
@validate(query=ListLogRequest)
async def list_log(request, query: ListLogRequest):
    """
    获取日志列表
    """
    db = request.app.ctx.db

    if query.operation_time_start:
        query.operation_time_start = timestamp_to_datetime(query.operation_time_start)
    if query.operation_time_end:
        query.operation_time_end = timestamp_to_datetime(query.operation_time_end)

    stmt = select(Log)
    if query.kw:
        stmt = stmt.where(
            or_(
                Log.content.like(f"%{query.kw}%"),
                Log.log_type.like(f"%{query.kw}%"),
                Log.user_name.like(f"%{query.kw}%"),
                Log.user_employee_id.like(f"%{query.kw}%"),
                Log.operation_ip.like(f"%{query.kw}%"),
            )
        )
    if query.log_type:
        stmt = stmt.where(Log.log_type.__eq__(query.log_type))
    if query.user_id:
        stmt = stmt.where(Log.user_id.__eq__(query.user_id))
    if query.user_name:
        stmt = stmt.where(Log.user_name.__eq__(query.user_name))
    if query.user_employee_id:
        stmt = stmt.where(Log.user_employee_id.__eq__(query.user_employee_id))
    if query.user_type:
        stmt = stmt.where(Log.user_type.__eq__(query.user_type))
    if query.operation_time_start:
        stmt = stmt.where(Log.operation_time >= query.operation_time_start)
    if query.operation_time_end:
        stmt = stmt.where(Log.operation_time <= query.operation_time_end)
    if query.operation_ip:
        stmt = stmt.where(Log.operation_ip.__eq__(query.operation_ip))

    with db() as session:
        total = session.execute(
            select(func.count(1)).select_from(stmt.alias("t"))
        ).scalar()
        if query.order_by:
            stmt = stmt.order_by(
                # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
                getattr(getattr(Log, query.order_by), query.asc and "asc" or "desc")()
            )
        stmt = stmt.offset(query.offset).limit(query.limit)
        logs = session.execute(stmt).scalars().all()
        logs = [LogSchema.model_validate(log) for log in logs]

        return BaseListResponse(
            data=logs,
            total=total,
            page_size=query.limit,
            page=query.page,
        ).json_response()
