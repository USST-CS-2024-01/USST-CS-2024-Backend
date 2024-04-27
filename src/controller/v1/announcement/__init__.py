from datetime import datetime

from sanic import Blueprint
from sanic_ext.extensions.openapi import openapi
from sqlalchemy import func, select, or_

import service.announcement
import service.class_
import service.file
import service.group
from controller.v1.announcement.request_model import (
    CreateAnnouncementRequest,
    ListAnnouncementRequest,
    UpdateAnnouncementRequest,
)
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import UserType, Announcement, AnnouncementReceiverType, User
from model.response_model import (
    BaseResponse,
    ErrorResponse,
    BaseListResponse,
    BaseDataResponse,
)
from model.schema import AnnouncementSchema
from util.parameter import generate_parameters_from_pydantic

announcement_bp = Blueprint("announcement", url_prefix="/announcement")


@announcement_bp.route("/create", methods=["POST"])
@openapi.summary("创建公告")
@openapi.tag("公告接口")
@openapi.description(
    """创建公告，需要提供标题、内容、接收者类型、接收者ID等信息。
    接收者类型包括individual、group、class、role、all，分别表示个人、小组、班级、角色、所有人。
    接收者ID根据接收者类型不同而不同，接收者ID为接收者的ID，接收者角色为接收者的角色。
    附件ID列表为附件的ID列表，可以为空。"""
)
@openapi.body(
    {
        "application/json": CreateAnnouncementRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(CreateAnnouncementRequest)
async def create_announcement(request, body: CreateAnnouncementRequest):
    """
    创建公告
    """
    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        announcement = Announcement(
            title=body.title,
            content=body.content,
            receiver_type=AnnouncementReceiverType(body.receiver_type),
        )
        field = "receiver_id"
        if body.receiver_type == "individual":
            announcement.receiver_user_id = body.receiver_id
        elif body.receiver_type == "group":
            announcement.receiver_group_id = body.receiver_id
            if not service.group.have_group_access_by_id(
                request, group_id=body.receiver_id
            ):
                return ErrorResponse.new_error(
                    code=403,
                    message="You don't have the permission to send announcement.",
                )
        elif body.receiver_type == "class":
            announcement.receiver_class_id = body.receiver_id
            if (
                not service.class_.has_class_access(request, class_id=body.receiver_id)
                or body.receiver_id == 1
            ):
                return ErrorResponse.new_error(
                    code=403,
                    message="You don't have the permission to send announcement.",
                )
        elif body.receiver_type == "role":
            if user.user_type != UserType.admin:
                return ErrorResponse.new_error(
                    code=403,
                    message="You don't have the permission to send announcement.",
                )
            announcement.receiver_role = UserType(body.receiver_role)
            field = "receiver_role"
        elif body.receiver_type == "all":
            if user.user_type != UserType.admin:
                return ErrorResponse.new_error(
                    code=403,
                    message="You don't have the permission to send announcement.",
                )

        if getattr(body, field) is None:
            return ErrorResponse.new_error(code=400, message=f"{field} is required")

        if body.attachments:
            for file_id in body.attachments:
                file, access = await service.file.check_has_access(request, file_id)
                if not access["read"]:
                    return ErrorResponse.new_error(
                        code=403,
                        message="You don't have the permission to send announcement.",
                    )
                announcement.attachment.append(file)

        announcement.publish_time = datetime.now()
        announcement.publisher = user.id

        session.merge(announcement)
        session.commit()
        session.refresh(announcement)

        request.app.ctx.log.add_log(
            request=request,
            user=user,
            log_type="announcement:create_announcement",
            content=f"User {user.username} created announcement {announcement.id}",
        )

    return BaseResponse().json_response()


@announcement_bp.route("/list", methods=["GET"])
@openapi.summary("获取公告列表")
@openapi.tag("公告接口")
@openapi.description(
    """获取公告列表，需要提供分页信息、排序字段、状态等信息。
    状态包括all、read、unread，分别表示所有、已读、未读。
    排序字段包括id、publish_time，分别表示ID、发布时间。"""
)
@openapi.definition(
    parameter=generate_parameters_from_pydantic(ListAnnouncementRequest)
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[AnnouncementSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@validate(query=ListAnnouncementRequest)
async def list_announcement(request, query: ListAnnouncementRequest):
    """
    获取公告列表
    """
    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        session.add(user)

        stmt = select(Announcement)
        if query.status == "read":
            stmt = stmt.filter(Announcement.read_users.any(User.id == user.id))
        elif query.status == "unread":
            stmt = stmt.filter(~Announcement.read_users.any(User.id == user.id))
        if query.order_by:
            stmt = stmt.order_by(getattr(Announcement, query.order_by).desc())

        # 筛选公告
        stmt = stmt.filter(
            or_(
                Announcement.publisher == user.id,
                Announcement.receiver_user_id == user.id,
                Announcement.receiver_group_id.in_([group.id for group in user.groups]),
                Announcement.receiver_class_id.in_(
                    [clazz.id for clazz in user.classes]
                ),
                Announcement.receiver_role == user.user_type,
                Announcement.receiver_type == AnnouncementReceiverType.all,
            )
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        stmt = stmt.limit(query.limit).offset(query.offset)

        result = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar()
        data = []
        for announcement in result:
            ann = AnnouncementSchema.model_validate(announcement)
            ann.read = user.id in [user.id for user in announcement.read_users]
            data.append(ann)

        return BaseListResponse(
            data=data,
            page=query.page,
            page_size=query.limit,
            total=total,
        ).json_response()


@announcement_bp.route("/<announcement_id:int>/read", methods=["POST"])
@openapi.summary("标记公告已读")
@openapi.tag("公告接口")
@openapi.description("标记公告已读，需要提供公告ID。")
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
async def read_announcement(request, announcement_id: int):
    try:
        announcement = service.announcement.get_announcement(request, announcement_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=404, message=str(e))

    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        session.add(user)
        session.add(announcement)
        announcement.read_users.append(user)
        session.commit()

    return BaseResponse().json_response()


@announcement_bp.route("/<announcement_id:int>", methods=["GET"])
@openapi.summary("获取公告详情")
@openapi.tag("公告接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[AnnouncementSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_announcement(request, announcement_id: int):
    try:
        announcement = service.announcement.get_announcement(request, announcement_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=404, message=str(e))

    db = request.app.ctx.db

    with db() as session:
        session.add(announcement)
        ann = AnnouncementSchema.model_validate(announcement)
        ann.read = request.ctx.user.id in [user.id for user in announcement.read_users]
        return BaseDataResponse(data=ann).json_response()


@announcement_bp.route("/<announcement_id:int>", methods=["PUT"])
@openapi.summary("更新公告")
@openapi.tag("公告接口")
@openapi.description(
    """更新公告，需要提供标题、内容、附件ID列表等信息。
    附件ID列表为附件的ID列表，可以为空。"""
)
@openapi.body(
    {
        "application/json": UpdateAnnouncementRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(json=UpdateAnnouncementRequest)
async def update_announcement(
    request, announcement_id: int, body: UpdateAnnouncementRequest
):
    try:
        announcement = service.announcement.get_announcement(request, announcement_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=404, message=str(e))

    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        session.add(announcement)
        session.add(user)

        if announcement.publisher != user.id:
            return ErrorResponse.new_error(
                code=403,
                message="You don't have the permission to update the announcement.",
            )

        if body.title:
            announcement.title = body.title
        if body.content:
            announcement.content = body.content
        if body.attachments is not None:
            announcement.attachment.clear()
            for file_id in body.attachments:
                file, access = await service.file.check_has_access(request, file_id)
                if not access["read"]:
                    return ErrorResponse.new_error(
                        code=403,
                        message="You don't have the permission to send announcement.",
                    )
                announcement.attachment.append(file)

        session.merge(announcement)
        session.commit()

        request.app.ctx.log.add_log(
            request=request,
            user=user,
            log_type="announcement:update_announcement",
            content=f"User {user.username} updated announcement {announcement.id}",
        )

    return BaseResponse().json_response()


@announcement_bp.route("/<announcement_id:int>", methods=["DELETE"])
@openapi.summary("删除公告")
@openapi.tag("公告接口")
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
async def delete_announcement(request, announcement_id: int):
    try:
        announcement = service.announcement.get_announcement(request, announcement_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=404, message=str(e))

    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        session.add(announcement)
        session.add(user)

        if announcement.publisher != user.id and user.user_type != UserType.admin:
            return ErrorResponse.new_error(
                code=403,
                message="You don't have the permission to delete the announcement.",
            )

        session.delete(announcement)
        session.commit()

        request.app.ctx.log.add_log(
            request=request,
            user=user,
            log_type="announcement:delete_announcement",
            content=f"User {user.username} deleted announcement {announcement.id}",
        )

    return BaseResponse().json_response()
