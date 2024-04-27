from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, select, func, or_

import service.class_
import service.file
import service.group
import service.task
from controller.v1.task.request_model import (
    CreateTaskRequest,
    SetTaskSequenceRequest,
    UpdateTaskRequest,
)
from controller.v1.task.response_model import TaskChainResponse
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Task, GroupRole, ClassMember, Group, GroupMemberRole
from model.enum import UserType, ClassStatus, GroupMemberRoleStatus, GroupStatus
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
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[TaskSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
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
@openapi.body(
    {
        "application/json": CreateTaskRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
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

    request.app.ctx.log.add_log(
        request=request,
        log_type="task:create",
        content=f"Create task {new.name} in class {class_id}",
    )

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
@openapi.body(
    {
        "application/json": SetTaskSequenceRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
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
    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    try:
        service.class_.change_class_task_sequence(request, class_id, body.sequences)
    except ValueError as e:
        return ErrorResponse.new_error(400, str(e))

    request.app.ctx.log.add_log(
        request=request,
        log_type="task:sequence",
        content=f"Set task sequence in class {class_id}",
    )

    return BaseResponse(code=200, message="ok").json_response()


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["PUT"])
@openapi.summary("更新班级任务")
@openapi.tag("任务接口")
@openapi.description("更新班级任务")
@openapi.body(
    {
        "application/json": UpdateTaskRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=UpdateTaskRequest)
async def update_class_task(
    request, class_id: int, task_id: int, body: UpdateTaskRequest
):
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
        update_dict["publish_time"] = timestamp_to_datetime(update_dict["publish_time"])
    if update_dict.get("deadline"):
        update_dict["deadline"] = timestamp_to_datetime(update_dict["deadline"])

    # 需要判定角色ID是否属于该班级
    check_role_stmt = (
        select(GroupRole)
        .where(
            and_(
                GroupRole.class_id == class_id,
                GroupRole.id == update_dict["specified_role"],
            )
        )
        .limit(1)
    )

    with db() as session:
        task = session.execute(
            select(Task)
            .where(and_(Task.id == task_id, Task.class_id == class_id))
            .limit(1)
        ).scalar_one_or_none()

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
        task.grade_percentage = update_dict.get(
            "grade_percentage", task.grade_percentage
        )

        session.commit()

    if update_dict.get("attached_files"):
        try:
            service.task.set_task_attachments(
                request, task_id, update_dict["attached_files"]
            )
        except ValueError as e:
            return ErrorResponse.new_error(400, str(e))

    request.app.ctx.log.add_log(
        request=request,
        log_type="task:update",
        content=f"Update task {task.name} in class {class_id}",
    )

    return BaseDataResponse(
        code=200,
        message="ok",
    ).json_response()


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["GET"])
@openapi.summary("获取班级任务")
@openapi.tag("任务接口")
@openapi.description("获取班级任务详情")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[TaskSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
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
    user = request.ctx.user

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

        # 授予临时文件访问权限
        files = task.attached_files
        file_ids = [file.id for file in files]
        for x in file_ids:
            await service.file.grant_file_access(request, x, user.id, {"read": True})

        return BaseDataResponse(
            code=200,
            message="ok",
            data=TaskSchema.model_validate(task),
        ).json_response()


@task_bp.route("/class/<class_id:int>/task/<task_id:int>", methods=["DELETE"])
@openapi.summary("删除班级任务")
@openapi.tag("任务接口")
@openapi.description(
    "删除班级任务，删除任务后，在前端需要重新设置任务顺序，否则会出现错误"
)
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

        locked_tasks = service.task.get_locked_tasks(request, class_id)
        locked_task_id = [t.id for t in locked_tasks]
        if task_id in locked_task_id:
            return ErrorResponse.new_error(
                400,
                "The task is locked and cannot be deleted",
            )

        session.delete(task)
        session.commit()

    request.app.ctx.log.add_log(
        request=request,
        log_type="task:delete",
        content=f"Delete task {task.name} in class {class_id}",
    )

    return BaseDataResponse(
        code=200,
        message="ok",
    ).json_response()


@task_bp.route("/class/<class_id:int>/task/start", methods=["POST"])
@openapi.summary("开始授课阶段")
@openapi.tag("任务接口")
@openapi.description(
    """进入授课阶段，此时需要满足以下条件，才能进入授课阶段：
    - 班级状态为`ClassStatus.grouping`
    - 所有班级成员均加入了小组，且小组成员申请状态为`GroupMemberStatus.approved`
    - 所有小组均设置了组长
    - 所有小组的状态为`GroupStatus.normal`
    - 班级的任务已经被完整设置（顺序被设置，且没有遗漏的任务）

进入授课阶段后，班级状态变更为`ClassStatus.teaching`，此时可以进行任务的发布、提交、评分等操作。
所有小组的当前任务ID被设置为班级的当前任务ID。
"""
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def start_teaching(request, class_id: int):
    db = request.app.ctx.db
    if class_id == 1:
        return ErrorResponse.new_error(
            400,
            "The default class cannot be started",
        )

    clazz = has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            400,
            "Class status is not `grouping`",
        )

    with db() as session:
        # 检查所有班级成员，是否都加入了小组，且小组成员申请状态为`GroupMemberStatus.approved`
        stmt_group_member_count = select(func.count(ClassMember.id)).where(
            and_(
                ClassMember.class_id == class_id,
                or_(
                    ClassMember.group_id.is_(None),
                    ClassMember.status != GroupMemberRoleStatus.approved,
                ),
                ClassMember.is_teacher.is_(False),
            )
        )

        group_member_count = session.execute(stmt_group_member_count).scalar()
        if group_member_count > 0:
            return ErrorResponse.new_error(
                400,
                "Some class members have not joined the group or have not been approved",
            )

        # 检查所有小组是否都为`GroupStatus.normal`
        stmt_abnormal_group_count = select(func.count(Group.id)).where(
            and_(
                Group.class_id == class_id,
                Group.status != GroupStatus.normal,
            )
        )

        abnormal_group_count = session.execute(stmt_abnormal_group_count).scalar()
        if abnormal_group_count > 0:
            return ErrorResponse.new_error(
                400,
                "Some groups are not normal",
            )

        # 检查所有小组是否都设置了组长
        stmt_group_leader_count = (
            select(func.count(GroupMemberRole.class_member_id))
            .select_from(GroupMemberRole)
            .join(ClassMember, GroupMemberRole.class_member)
            .where(
                and_(
                    ClassMember.class_id == class_id,
                    GroupMemberRole.role.has(is_manager=True),
                )
            )
        )

        group_leader_count = session.execute(stmt_group_leader_count).scalar()
        stmt_group_count = select(func.count(Group.id)).where(
            Group.class_id == class_id
        )
        group_count = session.execute(stmt_group_count).scalar()

        if group_leader_count != group_count:
            return ErrorResponse.new_error(
                400,
                "Some groups do not have a leader or have multiple leaders",
            )

    # 检查所有班级任务是否都已经设置
    try:
        service.task.check_task_chain(request, class_id)
    except ValueError as e:
        return ErrorResponse.new_error(400, str(e))

    # 更新班级状态
    with db() as session:
        session.add(clazz)
        clazz.status = ClassStatus.teaching

        # 将每个小组的当前任务ID设置为班级的当前任务ID
        session.execute(
            Group.__table__.update()
            .where(Group.class_id == class_id)
            .values(current_task_id=clazz.first_task_id)
        )

        session.commit()

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:start_teaching",
        content=f"Start teaching in class {class_id}",
    )

    return BaseResponse(code=200, message="ok").json_response()


@task_bp.route("/class/<class_id:int>/group/<group_id:int>/task_chain", methods=["GET"])
@openapi.summary("获取小组任务链")
@openapi.tag("任务接口")
@openapi.description("获取小组任务链")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": TaskChainResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_group_task_chain(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    group, group_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            404,
            "Group Not Found",
        )

    try:
        task_chain = service.task.get_group_locked_tasks(request, class_id, group_id)
    except ValueError as e:
        return ErrorResponse.new_error(400, str(e))
    current_task_id = group.current_task_id

    with db() as session:
        for task in task_chain:
            session.add(task)
        return TaskChainResponse(
            task_chain=[TaskSchema.model_validate(task) for task in task_chain],
            current_task_id=current_task_id,
        ).json_response()
