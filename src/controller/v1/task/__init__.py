from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, select

import service.class_
from controller.v1.class_.request_model import ListClassRequest
from controller.v1.task.request_model import CreateTaskRequest, SetTaskSequenceRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Task, GroupRole
from model.enum import UserType
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    BaseResponse,
    ErrorResponse,
)
from model.schema import TaskSchema
from service.class_ import has_class_access
from util.string import timestamp_to_datetime

task_bp = Blueprint("task")


@task_bp.route("/class/<class_id:int>/task/list", methods=["GET"])
@openapi.summary("获取班级任务列表")
@openapi.tag("任务接口")
@openapi.description("获取班级任务列表")
@need_login()
async def list_class_tasks(request, class_id: int):
    """
    获取班级任务列表
    :param request: Request
    :param class_id: Class ID
    :return: Class task list
    """
    # user = request.ctx.user
    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    stmt = select(Task).where(Task.class_id == class_id)

    with db() as session:
        result = session.execute(stmt).scalars().all()
        return BaseListResponse(
            data=[TaskSchema.model_validate(item) for item in result],
            total=len(result),
            page=1,
            page_size=len(result),
        ).json_response()


@task_bp.route("/class/<class_id:int>/task/create", methods=["POST"])
@openapi.summary("创建班级任务")
@openapi.tag("任务接口")
@openapi.description("创建班级任务")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=CreateTaskRequest)
async def create_class_task(request, class_id: int, body: CreateTaskRequest):
    """
    创建班级任务
    :param request: Request
    :param class_id: Class ID
    :param body: Task schema
    :return: Task
    """
    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    insert_dict = body.dict()

    # 创建一个新的 Task 对象
    insert_dict["publish_time"] = timestamp_to_datetime(insert_dict["publish_time"])
    insert_dict["deadline"] = timestamp_to_datetime(insert_dict["deadline"])

    new = Task(**insert_dict)

    # 需要判定角色ID是否属于该班级
    check_role_stmt = (
        select(GroupRole)
        .where(and_(GroupRole.class_id == class_id, GroupRole.id == new.specified_role))
        .limit(1)
    )

    new.class_id = class_id
    new_pydantic: TaskSchema

    with db() as session:
        result = session.execute(check_role_stmt).scalar_one_or_none()
        if not result:
            return ErrorResponse.new_error(
                400,
                "Invalid role id, please ensure the role belongs to the class",
            )

        # 添加到会话并提交，这将自动填充 id 属性
        session.add(new)
        session.commit()
        # 刷新对象，以获取数据库中的所有字段
        session.refresh(new)
        new_pydantic = TaskSchema.model_validate(new)

    return BaseDataResponse(
        code=200,
        message="ok",
        data=new_pydantic,
    ).json_response()


@task_bp.route("/class/<class_id:int>/task/sequence", methods=["POST"])
@openapi.summary("设置任务顺序")
@openapi.tag("任务接口")
@openapi.description(
    "设置任务顺序，传入任务ID列表，按照列表顺序设置任务顺序，需要将该班级下的所有任务ID传入，且不能出现重复ID"
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=SetTaskSequenceRequest)
async def set_task_sequence(request, class_id: int, body: SetTaskSequenceRequest):
    """
    设置任务顺序
    :param request: Request
    :param class_id: Class ID
    :param body: List of task IDs
    :return: Success response
    """
    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    try:
        service.class_.change_class_task_sequence(db, class_id, body.sequences)
    except ValueError as e:
        return ErrorResponse.new_error(400, str(e))

    return BaseResponse(code=200, message="ok").json_response()
