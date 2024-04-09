from operator import and_

from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select
from sqlalchemy.orm import subqueryload

import service.class_
from controller.v1.grouping.request_model import CreateGroupingRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Group, ClassMember, GroupMemberRole, GroupRole
from model.enum import UserType, ClassStatus, GroupStatus, GroupMemberRoleStatus
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    ErrorResponse,
)
from model.schema import GroupSchema

grouping_bp = Blueprint("grouping")


@grouping_bp.route("/class/<class_id:int>/grouping/start", methods=["POST"])
@openapi.summary("开始分组")
@openapi.tag("分组接口")
@openapi.description(
    "将班级状态推进为分组中状态，此时学生可以进行分组操作，老师可以进行分组设置和审核，班级状态的变更无法回退，需要谨慎操作。"
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
def start_grouping(request, class_id: int):
    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    if clazz.status != ClassStatus.not_started:
        return ErrorResponse.new_error(
            403,
            "Class is not in not started status",
        )

    with db() as session:
        clazz.status = ClassStatus.grouping
        session.add(clazz)
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@grouping_bp.route("/class/<class_id:int>/grouping/list", methods=["GET"])
@openapi.summary("查询分组列表")
@openapi.tag("分组接口")
@need_login()
def get_grouping_list(request, class_id: int):
    db = request.app.ctx.db

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    stmt = (
        select(Group)
        .options(
            subqueryload(Group.members).joinedload(ClassMember.user),
            subqueryload(Group.members).joinedload(ClassMember.roles),
        )
        .where(Group.class_id == class_id)
    )

    with db() as session:
        groups = session.execute(stmt).scalars().all()
        # 加载信息，由于使用了lazyLoad，会导致GroupSchema中的members解析会出现问题

    return BaseListResponse(
        data=[GroupSchema.from_orm(group) for group in groups],
        total=len(groups),
        page=1,
        page_size=len(groups),
    ).json_response()


@grouping_bp.route("/class/<class_id:int>/grouping/create", methods=["POST"])
@openapi.summary("创建分组")
@openapi.tag("分组接口")
@need_login()
@validate(json=CreateGroupingRequest)
def create_grouping(request, class_id: int, body: CreateGroupingRequest):
    # 这个参数只有老师可以传
    if request.ctx.user.user_type == UserType.student:
        body.leader = request.ctx.user.id
    elif request.ctx.user.user_type == UserType.teacher and body.leader is None:
        return ErrorResponse.new_error(
            400,
            "Leader is required",
        )

    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            403,
            "Class is not in grouping status",
        )

    with db() as session:
        # 检查是否已经有分组
        stmt = select(ClassMember).where(
            ClassMember.class_id == class_id, ClassMember.user_id == body.leader
        )

        result = session.execute(stmt).scalar()
        if not result:
            return ErrorResponse.new_error(
                404,
                "Leader not found in class",
            )

        if result.group_id is not None:
            return ErrorResponse.new_error(
                400,
                "Leader already in a group",
            )

        group = Group(
            class_id=class_id,
            name=body.name,
            status=GroupStatus.pending,
        )
        session.add(group)
        session.flush()

        # 更新班级成员的分组信息
        stmt = (
            ClassMember.__table__.update()
            .where(
                and_(
                    ClassMember.class_id == class_id,
                    ClassMember.user_id == body.leader,
                )
            )
            .values(group_id=group.id)
        )

        session.execute(stmt)

        # 新增组长信息
        leader = session.execute(
            select(GroupRole).where(
                GroupRole.class_id == class_id,
                GroupRole.is_manager.is_(True),
            )
        ).scalar()
        if not leader:
            return ErrorResponse.new_error(
                500,
                "Leader role not found in class config",
            )

        gmr = GroupMemberRole(
            class_member_id=result.id,
            role_id=leader.id,
            status=GroupMemberRoleStatus.approved,
        )
        session.add(gmr)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@grouping_bp.route(
    "/class/<class_id:int>/grouping/<group_id:int>/member/<class_member_id:int>",
    methods=["POST"],
)
@openapi.summary("加入分组")
@openapi.tag("分组接口")
@openapi.description(
    """申请加入一个分组，或者组长邀请特定成员加入分组，或者教师将特定成员加入分组。
若是自行申请加入分组，则class_member_id将被强制替换为当前用户在班级中的id。
若用户已经在一个组中，则无法加入新组；若用户先前申请了加入组，或者被邀请加入组，则再次申请时，将会覆盖之前的申请。"""
)
@need_login()
def join_grouping(request, class_id: int, group_id: int, class_member_id: int):
    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            403,
            "Class is not in grouping status",
        )

    with db() as session:
        group = session.execute(
            select(Group).where(Group.id == group_id, Group.class_id == class_id)
        ).scalar()
        if not group:
            return ErrorResponse.new_error(
                404,
                "Group Not Found",
            )

        # 若该分组被教师审核通过，则无法加入
        if group.status != GroupStatus.pending:
            return ErrorResponse.new_error(
                403,
                "Group is not in pending status",
            )

        class_member_stmt = select(ClassMember).where(
            ClassMember.class_id == class_id,
            ClassMember.id == class_member_id,
        )
        if request.ctx.user.user_type == UserType.student:
            class_member_stmt = class_member_stmt.where(
                ClassMember.user_id == request.ctx.user.id
            )
        class_member = session.execute(class_member_stmt).scalar()
        if not class_member:
            return ErrorResponse.new_error(
                404,
                "Class Member Not Found",
            )

        # 若用户已经在一个组中，则无法加入新组
        if (
            class_member.group_id is not None
            and class_member.status == GroupMemberRoleStatus.approved
        ):
            return ErrorResponse.new_error(
                400,
                "Class Member already in a group",
            )

        # 判断这个小组是否已经满员（满员条件：小组成员数量 >= 小组角色数量）
        role_list = (
            session.execute(
                select(GroupRole).where(
                    GroupRole.class_id == class_id,
                )
            )
            .scalars()
            .all()
        )

        role_count = len(role_list)
        if len(group.members) >= role_count:
            return ErrorResponse.new_error(
                400,
                "Group is full",
            )

        if request.ctx.user.user_type == UserType.student:
            if class_member.user_id != request.ctx.user.id:  # 队长邀请队员
                request_status = GroupMemberRoleStatus.member_review
            else:  # 自行申请
                request_status = GroupMemberRoleStatus.leader_review
        elif (
            request.ctx.user.user_type == UserType.teacher
            or request.ctx.user.user_type == UserType.admin
        ):
            request_status = GroupMemberRoleStatus.approved

        # 更新班级成员的分组信息
        stmt = (
            ClassMember.__table__.update()
            .where(
                and_(
                    ClassMember.class_id == class_id,
                    ClassMember.id == class_member_id,
                )
            )
            .values(group_id=group_id, status=request_status)
        )

        session.execute(stmt)
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@grouping_bp.route(
    "/class/<class_id:int>/grouping/<group_id:int>/member/<class_member_id:int>",
    methods=["DELETE"],
)
@openapi.summary("退出分组")
@openapi.tag("分组接口")
@openapi.description(
    """退出一个分组，或者组长将特定成员移出分组，或者教师将特定成员移出分组。
若用户已经在一个组中，则无法退出；若用户先前申请了加入组，或者被邀请加入组，则退出时，将会取消之前的申请。"""
)
@need_login()
def leave_grouping(request, class_id: int, group_id: int, class_member_id: int):
    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            403,
            "Class is not in grouping status",
        )

    with db() as session:
        group = session.execute(
            select(Group).where(Group.id == group_id, Group.class_id == class_id)
        ).scalar()
        if not group:
            return ErrorResponse.new_error(
                404,
                "Group Not Found",
            )
        if group.status != GroupStatus.pending:
            return ErrorResponse.new_error(
                403,
                "Group is not in pending status",
            )

        self_class_member = session.execute(
            select(ClassMember).where(
                ClassMember.class_id == class_id,
                ClassMember.group_id == group_id,
                ClassMember.user_id == request.ctx.user.id,
                ClassMember.status == GroupMemberRoleStatus.approved,
            )
        ).scalar()

        class_member = session.execute(
            select(ClassMember).where(
                ClassMember.class_id == class_id,
                ClassMember.group_id == group_id,
                ClassMember.id == class_member_id,
            )
        ).scalar()
        if not class_member:
            return ErrorResponse.new_error(
                404,
                "The specified member is not in the group",
            )

        # 判断用户是否有权限退出特定成员
        if request.ctx.user.user_type == UserType.student:
            if not self_class_member:
                return ErrorResponse.new_error(
                    403,
                    "You are not in this group",
                )
            is_leader = False
            for role in self_class_member.roles:
                if role.is_manager:
                    is_leader = True
                    break
            if self_class_member.id != class_member_id and not is_leader:
                return ErrorResponse.new_error(
                    403,
                    "You can only leave yourself",
                )
            elif is_leader and self_class_member.id == class_member_id:
                return ErrorResponse.new_error(
                    403,
                    "Leader cannot leave group",
                )

        # 更新班级成员的分组信息
        stmt = (
            ClassMember.__table__.update()
            .where(
                and_(
                    ClassMember.class_id == class_id,
                    ClassMember.id == class_member_id,
                )
            )
            .values(group_id=None, status=None)
        )

        session.execute(stmt)
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()
