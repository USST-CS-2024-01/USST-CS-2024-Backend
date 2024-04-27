import time

from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select, func, and_

import service.class_
import service.file
import service.group
import service.group_meeting
import service.group_task
import service.role
import service.task
from controller.v1.group_meeting.request_model import (
    ListGroupMeetingRequest,
    CreateGroupMeetingRequest,
    UpdateGroupMeetingRequest,
)
from middleware.auth import need_login
from middleware.validator import validate
from model import GroupMeeting, GroupMeetingParticipant
from model.response_model import (
    BaseListResponse,
    ErrorResponse,
    BaseDataResponse,
)
from model.schema import GroupMeetingSchema
from util.parameter import generate_parameters_from_pydantic
from util.string import timestamp_to_datetime

group_meeting_bp = Blueprint("group_meeting")


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/list", methods=["GET"]
)
@openapi.summary("获取分组会议列表")
@openapi.tag("会议接口")
@openapi.definition(
    parameter=generate_parameters_from_pydantic(ListGroupMeetingRequest)
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[GroupMeetingSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@validate(query=ListGroupMeetingRequest)
async def get_meeting_list(
    request, class_id: int, group_id: int, query: ListGroupMeetingRequest
):
    db = request.app.ctx.db

    group, member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    stmt = select(GroupMeeting).filter(GroupMeeting.group_id.__eq__(group_id))

    if query.kw:
        stmt = stmt.filter(GroupMeeting.name.ilike(f"%{query.kw}%"))
    if query.task_id:
        stmt = stmt.filter(GroupMeeting.task_id.__eq__(query.task_id))

    if query.order_by:
        stmt = stmt.order_by(
            # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
            getattr(
                getattr(GroupMeeting, query.order_by), query.asc and "asc" or "desc"
            )()
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())

    with db() as session:
        meetings = session.execute(stmt).scalars().all()
        count = session.execute(count_stmt).scalar()

        return BaseListResponse(
            data=[GroupMeetingSchema.model_validate(meeting) for meeting in meetings],
            total=count,
        ).json_response()


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/<meeting_id:int>",
    methods=["GET"],
)
@openapi.summary("获取分组会议详情")
@openapi.tag("会议接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[GroupMeetingSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_meeting_detail(request, class_id: int, group_id: int, meeting_id: int):
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
        meeting = session.execute(
            select(GroupMeeting).filter(
                and_(
                    GroupMeeting.id.__eq__(meeting_id),
                    GroupMeeting.group_id.__eq__(group_id),
                )
            )
        ).scalar_one_or_none()
        if not meeting:
            return ErrorResponse.new_error(
                code=404,
                message="Meeting not found",
            )

        return BaseDataResponse(
            data=GroupMeetingSchema.model_validate(meeting)
        ).json_response()


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/<meeting_id:int>",
    methods=["DELETE"],
)
@openapi.summary("删除分组会议")
@openapi.tag("会议接口")
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
async def delete_meeting(request, class_id: int, group_id: int, meeting_id: int):
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
        meeting = session.execute(
            select(GroupMeeting).filter(
                and_(
                    GroupMeeting.id.__eq__(meeting_id),
                    GroupMeeting.group_id.__eq__(group_id),
                )
            )
        ).scalar_one_or_none()
        if not meeting:
            return ErrorResponse.new_error(
                code=404,
                message="Meeting not found",
            )

        # 已经到开始时间的会议不能删除
        if meeting.start_time.timestamp() < time.time():
            return ErrorResponse.new_error(
                code=403,
                message="Meeting has started",
            )

        # 判断是否有权限删除
        if not is_manager and not service.role.check_user_has_role(
            request, class_id, user_id, [meeting.publisher]
        ):
            return ErrorResponse.new_error(
                code=403,
                message="Permission denied",
            )

        session.delete(meeting)
        session.commit()
        return BaseDataResponse().json_response()


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/<meeting_id:int>",
    methods=["PUT"],
)
@openapi.summary("更新分组会议")
@openapi.tag("会议接口")
@openapi.body(
    {
        "application/json": UpdateGroupMeetingRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(json=UpdateGroupMeetingRequest)
async def update_meeting(
    request,
    class_id: int,
    group_id: int,
    meeting_id: int,
    body: UpdateGroupMeetingRequest,
):
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
        meeting = session.execute(
            select(GroupMeeting).filter(
                and_(
                    GroupMeeting.id.__eq__(meeting_id),
                    GroupMeeting.group_id.__eq__(group_id),
                )
            )
        ).scalar_one_or_none()
        if not meeting:
            return ErrorResponse.new_error(
                code=404,
                message="Meeting not found",
            )

        # 已经到开始时间的会议不能修改
        if meeting.start_time.timestamp() < time.time():
            return ErrorResponse.new_error(
                code=403,
                message="Meeting has started",
            )

        # 判断是否有权限修改
        if not is_manager and not service.role.check_user_has_role(
            request, class_id, user_id, [meeting.publisher]
        ):
            return ErrorResponse.new_error(
                code=403,
                message="Permission denied",
            )

        if body.start_time and body.start_time < time.time():
            return ErrorResponse.new_error(
                code=400,
                message="Meeting start time is invalid",
            )

        if body.end_time and body.end_time < body.start_time:
            return ErrorResponse.new_error(
                code=400,
                message="Meeting end time is invalid",
            )

        if body.related_files:
            files = service.file.check_file_in_group(
                request, group_id, body.related_files
            )
            service.group_meeting.update_group_meeting_attachment(
                request, meeting_id, [file.id for file in files]
            )

        meeting.name = body.name or meeting.name
        meeting.start_time = (
            timestamp_to_datetime(body.start_time) or meeting.start_time
        )
        meeting.end_time = timestamp_to_datetime(body.end_time) or meeting.end_time
        meeting.meeting_type = body.meeting_type or meeting.meeting_type
        meeting.meeting_link = body.meeting_link or meeting.meeting_link

        session.add(meeting)
        session.commit()

    return BaseDataResponse().json_response()


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/create",
    methods=["POST"],
)
@openapi.summary("创建分组会议")
@openapi.tag("会议接口")
@openapi.body(
    {
        "application/json": CreateGroupMeetingRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[GroupMeetingSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@validate(json=CreateGroupMeetingRequest)
async def create_meeting(
    request, class_id: int, group_id: int, body: CreateGroupMeetingRequest
):
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

    current_task = service.task.get_current_task(request, group_id)
    if not is_manager and not service.role.check_user_has_role(
        request, class_id, user_id, [current_task.specified_role]
    ):
        return ErrorResponse.new_error(
            code=403,
            message="You don't have permission to create meeting",
        )

    if body.start_time < time.time():
        return ErrorResponse.new_error(
            code=400,
            message="Meeting start time is invalid",
        )

    if body.end_time < body.start_time:
        return ErrorResponse.new_error(
            code=400,
            message="Meeting end time is invalid",
        )

    with db() as session:
        meeting = GroupMeeting(
            name=body.name,
            start_time=timestamp_to_datetime(body.start_time),
            end_time=timestamp_to_datetime(body.end_time),
            meeting_type=body.meeting_type,
            meeting_link=body.meeting_link,
            task_id=current_task.id,
            publisher=current_task.specified_role,
            group_id=group_id,
        )
        if body.related_files:
            files = service.file.check_file_in_group(
                request, group_id, body.related_files
            )
            meeting.related_files.extend(files)

        session.add(meeting)
        session.commit()

        return BaseDataResponse(
            data=GroupMeetingSchema.model_validate(meeting)
        ).json_response()


@group_meeting_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/meeting/<meeting_id:int>/attend",
    methods=["POST"],
)
@openapi.summary("参加分组会议")
@openapi.tag("会议接口")
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
async def attend_meeting(request, class_id: int, group_id: int, meeting_id: int):
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
        meeting = session.execute(
            select(GroupMeeting).filter(
                and_(
                    GroupMeeting.id.__eq__(meeting_id),
                    GroupMeeting.group_id.__eq__(group_id),
                )
            )
        ).scalar_one_or_none()
        if not meeting:
            return ErrorResponse.new_error(
                code=404,
                message="Meeting not found",
            )

        if meeting.start_time.timestamp() > time.time():
            return ErrorResponse.new_error(
                code=403,
                message="Meeting has not started",
            )
        if meeting.end_time.timestamp() < time.time():
            return ErrorResponse.new_error(
                code=403,
                message="Meeting has ended",
            )

        if user_id not in [participant.id for participant in meeting.participants]:
            stmt = GroupMeetingParticipant.__table__.insert().values(
                meeting_id=meeting_id, user_id=user_id
            )
            session.execute(stmt)
            session.commit()

        return BaseDataResponse().json_response()
