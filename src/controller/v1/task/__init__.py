from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, func, select, or_

from controller.v1.class_.request_model import ListClassRequest
from controller.v1.class_.response_model import ClassReturnItem
from controller.v1.task.request_model import CreateTaskRequest
from middleware.auth import need_login
from middleware.validator import validate
from model import Class, ClassMember, Task, GroupRole
from model.enum import UserType
from model.response_model import BaseDataResponse, BaseListResponse, BaseResponse, ErrorResponse
from model.schema import ClassSchema, TaskSchema
from service.class_ import has_class_access
from util.string import timestamp_to_datetime

task_bp = Blueprint("task")


@task_bp.route("/class/<class_id:int>/task/list", methods=["GET"])
@openapi.summary("获取班级任务列表")
@openapi.tag("任务接口")
@openapi.description("获取班级任务列表")
@need_login()
def list_class_tasks(request, class_id: int):
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
            data=[TaskSchema.from_orm(item) for item in result],
            total=len(result),
            page=1,
            page_size=len(result),
        ).json_response()


@task_bp.route("/class/<class_id:int>/task/create", methods=["POST"])
@openapi.summary("创建班级任务")
@openapi.tag("任务接口")
@openapi.description("创建班级任务")
@need_login()
@validate(json=CreateTaskRequest)
def create_class_task(request, class_id: int, body: CreateTaskRequest):
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
        select(GroupRole).where(
            and_(
                GroupRole.class_id == class_id,
                GroupRole.id == new.specified_role
            )
        ).limit(1)
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
        new_pydantic = TaskSchema.from_orm(new)

    return BaseDataResponse(
        code=200,
        message="ok",
        data=new_pydantic,
    ).json_response()
