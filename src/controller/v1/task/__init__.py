from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, select

import service.class_
import service.task
from controller.v1.class_.request_model import ListClassRequest
from controller.v1.task.request_model import CreateTaskRequest, SetTaskSequenceRequest, UpdateTaskRequest
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
    del insert_dict["attached_files"]

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

        session.refresh(new)

    try:
        if body.attached_files:
            service.task.set_task_attachments(request, new.id, body.attached_files)
    except ValueError as e:
        ErrorResponse.new_error(400, str(e))

    return BaseDataResponse(
        code=200,
        message="ok",
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


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["PUT"])
@openapi.summary("更新班级任务")
@openapi.tag("任务接口")
@openapi.description("更新班级任务")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=UpdateTaskRequest)
async def update_class_task(request, class_id: int, task_id: int, body: UpdateTaskRequest):
    """
    更新班级任务
    :param request: Request
    :param class_id: Class ID
    :param task_id: Task ID
    :param body: Task schema
    :return: Task
    """

    db = request.app.ctx.db
    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    update_dict = body.dict(exclude_unset=True)
    if len(update_dict) == 0:
        return ErrorResponse.new_error(
            400,
            "Nothing to update",
        )
    if update_dict.get("publish_time"):
        update_dict["publish_time"] = timestamp_to_datetime(
            update_dict["publish_time"]
        )
    if update_dict.get("deadline"):
        update_dict["deadline"] = timestamp_to_datetime(update_dict["deadline"])

    # 需要判定角色ID是否属于该班级
    check_role_stmt = (
        select(GroupRole)
        .where(and_(GroupRole.class_id == class_id, GroupRole.id == update_dict["specified_role"]))
        .limit(1)
    )

    with db() as session:
        task = session.execute(
            select(Task)
            .where(and_(Task.id == task_id, Task.class_id == class_id))
            .limit(1)
        ).scalar_one_or_none()

        # TODO 判断班级状态、班级小组进度

        if not task:
            return ErrorResponse.new_error(
                400,
                "Task not found",
            )

        if update_dict.get("specified_role"):
            result = session.execute(check_role_stmt).scalar_one_or_none()
            if not result:
                return ErrorResponse.new_error(
                    400,
                    "Invalid role id, please ensure the role belongs to the class",
                )
            task.specified_role = update_dict["specified_role"]

        task.name = update_dict.get("name", task.name)
        task.content = update_dict.get("content", task.content)
        task.publish_time = update_dict.get("publish_time", task.publish_time)
        task.deadline = update_dict.get("deadline", task.deadline)
        task.grade_percentage = update_dict.get("grade_percentage", task.grade_percentage)

        session.commit()

    if update_dict.get("attached_files"):
        try:
            service.task.set_task_attachments(request, task_id, update_dict["attached_files"])
        except ValueError as e:
            return ErrorResponse.new_error(400, str(e))

    return BaseDataResponse(
        code=200,
        message="ok",
    ).json_response()


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["GET"])
@openapi.summary("获取班级任务")
@openapi.tag("任务接口")
@openapi.description("获取班级任务详情")
@need_login()
async def get_class_task(request, class_id: int, task_id: int):
    """
    获取班级任务
    :param request: Request
    :param class_id: Class ID
    :param task_id: Task ID
    :return: Task
    """

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    db = request.app.ctx.db

    with db() as session:
        task = session.execute(
            select(Task)
            .where(and_(Task.id == task_id, Task.class_id == class_id))
            .limit(1)
        ).scalar_one_or_none()

        if not task:
            return ErrorResponse.new_error(
                404,
                "Task Not Found",
            )

        return BaseDataResponse(
            code=200,
            message="ok",
            data=TaskSchema.model_validate(task),
        ).json_response()


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["DELETE"])
@openapi.summary("删除班级任务")
@openapi.tag("任务接口")
@openapi.description("删除班级任务，删除任务后，在前端需要重新设置任务顺序，否则会出现错误")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def delete_class_task(request, class_id: int, task_id: int):
    """
    删除班级任务
    :param request: Request
    :param class_id: Class ID
    :param task_id: Task ID
    :return: Success response
    """

    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    with db() as session:
        task = session.execute(
            select(Task)
            .where(and_(Task.id == task_id, Task.class_id == class_id))
            .limit(1)
        ).scalar_one_or_none()

        if not task:
            return ErrorResponse.new_error(
                404,
                "Task Not Found",
            )

        # TODO 判断班级状态、班级小组进度

        session.delete(task)
        session.commit()

    return BaseDataResponse(
        code=200,
        message="ok",
    ).json_response()
