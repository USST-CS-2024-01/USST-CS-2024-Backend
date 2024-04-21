import datetime

from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload

import service.class_
import service.file
import service.group
import service.group_task
import service.role
import service.task
from controller.v1.group_task.request_model import (
    ListGroupTaskRequest,
    AddGroupTaskRequest,
    UpdateGroupTaskRequest,
)
from middleware.auth import need_login
from middleware.validator import validate
from model import GroupTask
from model.response_model import (
    BaseListResponse,
    ErrorResponse,
    BaseDataResponse,
)
from model.schema import GroupTaskSchema
from util.string import timestamp_to_datetime

group_task_bp = Blueprint("group_task")


@group_task_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/group_task/list", methods=["GET"]
)
@openapi.summary("获取小组任务列表")
@openapi.tag("小组任务接口")
@need_login()
@validate(query=ListGroupTaskRequest)
async def get_group_task_list(
    request, class_id: int, group_id: int, query: ListGroupTaskRequest
):
    """
    获取小组任务列表

    :param query:
    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID

    :return: Group task list
    """
    db = request.app.ctx.db

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    stmt = select(GroupTask).where(GroupTask.group_id.__eq__(group_id))

    if query.status:
        stmt = stmt.where(GroupTask.status.__eq__(query.status))
    if query.kw:
        stmt = stmt.where(GroupTask.name.ilike(f"%{query.kw}%"))
    if query.priority:
        stmt = stmt.where(GroupTask.priority.__eq__(query.priority))
    if query.order_by:
        stmt = stmt.order_by(
            # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
            getattr(getattr(GroupTask, query.order_by), query.asc and "asc" or "desc")()
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())

    with db() as session:
        task_list = session.execute(stmt).scalars().all()
        count = session.execute(count_stmt).scalar()
        resp_list = [GroupTaskSchema.model_validate(task) for task in task_list]

        return BaseListResponse(
            data=resp_list,
            total=count,
        ).json_response()


@group_task_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/group_task/<task_id:int>",
    methods=["GET"],
)
@openapi.summary("获取小组任务详情")
@openapi.tag("小组任务接口")
@need_login()
async def get_group_task_detail(request, class_id: int, group_id: int, task_id: int):
    """
    获取小组任务详情

    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID
    :param task_id: Task ID

    :return: Group task detail
    """
    db = request.app.ctx.db

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        task = session.execute(
            select(GroupTask).where(
                and_(
                    GroupTask.id.__eq__(task_id),
                    GroupTask.group_id.__eq__(group_id),
                )
            )
        ).scalar()

        if not task:
            return ErrorResponse.new_error(
                code=404,
                message="Task not found",
            )

        return BaseDataResponse(
            data=GroupTaskSchema.model_validate(task)
        ).json_response()


@group_task_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/group_task/create",
    methods=["POST"],
)
@openapi.summary("创建小组任务")
@openapi.tag("小组任务接口")
@need_login()
@validate(json=AddGroupTaskRequest)
async def create_group_task(
    request,
    body: AddGroupTaskRequest,
    class_id: int,
    group_id: int,
):
    """
    创建小组任务

    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID
    :param body: Request JSON

    :return: Group task detail
    """
    db = request.app.ctx.db

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    try:
        current_group_task = service.task.get_current_task(request, group_id)
    except ValueError as e:
        return ErrorResponse.new_error(
            code=400,
            message=str(e),
        )

    if not is_manager:
        if not member:
            return ErrorResponse.new_error(
                code=403,
                message="You are not a member of this group",
            )
        with db() as session:
            session.add(current_group_task)
            session.add(member)
            # 判断当前用户是否有权限创建任务(小组任务的创建权限依赖于当前小组正在执行任务的角色)
            if current_group_task.role not in member.roles:
                return ErrorResponse.new_error(
                    code=403,
                    message="You can't create task",
                )

    try:
        assignees = service.role.check_group_role_ids(request, class_id, body.assignees)
    except ValueError as e:
        return ErrorResponse.new_error(
            code=400,
            message=str(e),
        )
    if len(assignees) == 0:
        return ErrorResponse.new_error(
            code=400,
            message="Assignees can't be empty",
        )

    try:
        related_files = service.file.check_file_in_group(
            request, group_id, body.related_files
        )
    except ValueError as e:
        return ErrorResponse.new_error(
            code=400,
            message=str(e),
        )

    with db() as session:
        task = GroupTask(
            group_id=group_id,
            name=body.name,
            details=body.details,
            status="pending",
            publisher=request.ctx.user.id,
            deadline=timestamp_to_datetime(body.deadline) if body.deadline else None,
            priority=body.priority,
            publish_time=datetime.datetime.now(),
            update_time=datetime.datetime.now(),
        )
        task.assignees.extend(assignees)
        if len(related_files) > 0:
            task.related_files.extend(related_files)

        session.add(task)
        session.commit()

        return BaseDataResponse(
            data=GroupTaskSchema.model_validate(task)
        ).json_response()


@group_task_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/group_task/<task_id:int>",
    methods=["PUT"],
)
@openapi.summary("更新小组任务")
@openapi.tag("小组任务接口")
@need_login()
@validate(json=UpdateGroupTaskRequest)
async def update_group_task(
    request,
    body: UpdateGroupTaskRequest,
    class_id: int,
    group_id: int,
    task_id: int,
):
    """
    更新小组任务

    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID
    :param task_id: Task ID
    :param body: Request JSON

    :return: Group task detail
    """
    db = request.app.ctx.db
    user_id = request.ctx.user.id

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    update_dict = body.model_dump(exclude_unset=True)
    if len(update_dict) == 0:
        return ErrorResponse.new_error(
            code=400,
            message="Nothing to update",
        )

    update_dict.pop("assignees", None)
    update_dict.pop("related_files", None)

    with db() as session:
        group_task = session.execute(
            select(GroupTask)
            .options(
                joinedload(GroupTask.assignees), joinedload(GroupTask.related_files)
            )
            .where(
                and_(
                    GroupTask.id == task_id,
                    GroupTask.group_id == group_id,
                )
            )
        ).scalar()

        if not group_task:
            return ErrorResponse.new_error(
                code=404,
                message="Task not found",
            )

        # publisher 角色可以修改所有字段，assignees 可以修改 status 和 related_files
        if not group_task:
            return ErrorResponse.new_error(
                code=404,
                message="Task not found",
            )

        if (
            service.role.check_user_has_role(
                request, class_id, user_id, [group_task.publisher]
            )
            or is_manager
        ):
            group_task.update_time = datetime.datetime.now()
            # Handle assignees and related_files before general attributes
            if body.assignees:
                assignees = service.role.check_group_role_ids(
                    request, class_id, body.assignees
                )
                service.group_task.update_group_task_assignee(
                    request, task_id, [assignee.id for assignee in assignees]
                )
            if body.related_files is not None:
                related_files = service.file.check_file_in_group(
                    request, group_id, body.related_files
                )
                service.group_task.update_group_task_attachment(
                    request, task_id, [file.id for file in related_files]
                )

            # Update other attributes
            for key, value in update_dict.items():
                setattr(group_task, key, value)

        elif service.role.check_user_has_role(
            request,
            class_id,
            user_id,
            [assignee.id for assignee in group_task.assignees],
        ):
            if body.status:
                group_task.status = body.status
            if body.related_files is not None:
                related_files = service.file.check_file_in_group(
                    request, group_id, body.related_files
                )
                service.group_task.update_group_task_attachment(
                    request, task_id, [file.id for file in related_files]
                )
            group_task.update_time = datetime.datetime.now()
        else:
            return ErrorResponse.new_error(
                code=403,
                message="You can't update this task",
            )

        session.commit()

    return BaseDataResponse().json_response()


@group_task_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/group_task/<task_id:int>",
    methods=["DELETE"],
)
@openapi.summary("删除小组任务")
@openapi.tag("小组任务接口")
@need_login()
async def delete_group_task(request, class_id: int, group_id: int, task_id: int):
    """
    删除小组任务

    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID
    :param task_id: Task ID

    :return: Success response
    """
    db = request.app.ctx.db
    user_id = request.ctx.user.id

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        group_task = session.execute(
            select(GroupTask).where(
                and_(
                    GroupTask.id == task_id,
                    GroupTask.group_id == group_id,
                )
            )
        ).scalar()

        if not group_task:
            return ErrorResponse.new_error(
                code=404,
                message="Task not found",
            )

        if (
            service.role.check_user_has_role(
                request, class_id, user_id, [group_task.publisher]
            )
            or is_manager
        ):
            session.delete(group_task)
        else:
            return ErrorResponse.new_error(
                code=403,
                message="You can't delete this task",
            )

        session.commit()

    return BaseDataResponse().json_response()
