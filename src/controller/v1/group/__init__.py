from operator import and_

from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select
from sqlalchemy.orm import subqueryload

import service.class_
import service.group
from controller.v1.group.request_model import (
    CreateGroupRequest,
    UpdateGroupMemberRequest,
    UpdateGroupRequest,
)
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Group, ClassMember, GroupMemberRole, GroupRole
from model.enum import UserType, ClassStatus, GroupStatus, GroupMemberRoleStatus
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    ErrorResponse,
)
from model.schema import GroupSchema, ClassMemberSchema

group_bp = Blueprint("group")


@group_bp.route("/class/<class_id:int>/group/start", methods=["POST"])
@openapi.summary("开始分组")
@openapi.tag("分组接口")
@openapi.description(
    "将班级状态推进为分组中状态，此时学生可以进行分组操作，老师可以进行分组设置和审核，班级状态的变更无法回退，需要谨慎操作。"
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
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def start_group(request, class_id: int):
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
        session.add(clazz)

        # 检查组长角色是否设置，且只能有一个
        leader_count = 0
        for role in clazz.roles:
            if role.is_manager:
                leader_count += 1
        if leader_count != 1:
            return ErrorResponse.new_error(
                400,
                "Leader role was set incorrectly",
            )

        clazz.status = ClassStatus.grouping
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route("/class/<class_id:int>/group/list", methods=["GET"])
@openapi.summary("查询分组列表")
@openapi.tag("分组接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[GroupSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_group_list(request, class_id: int):
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
        data=[GroupSchema.model_validate(group) for group in groups],
        total=len(groups),
        page=1,
        page_size=len(groups),
    ).json_response()


@group_bp.route("/class/<class_id:int>/group/create", methods=["POST"])
@openapi.summary("创建分组")
@openapi.tag("分组接口")
@openapi.body(
    {
        "application/json": CreateGroupRequest.schema(
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
@need_login()
@validate(json=CreateGroupRequest)
async def create_group(request, class_id: int, body: CreateGroupRequest):
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
            "Class is not in group status",
        )

    with db() as session:
        # 检查是否已经有分组
        stmt = select(ClassMember).where(
            ClassMember.class_id == class_id,
            ClassMember.user_id == body.leader,
        )

        result = session.execute(stmt).scalar()
        if not result:
            return ErrorResponse.new_error(
                404,
                "Leader not found in class",
            )

        if (
            result.group_id is not None
            and result.status == GroupMemberRoleStatus.approved
        ):
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
            .values(group_id=group.id, status=GroupMemberRoleStatus.approved)
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

        gmr = GroupMemberRole(class_member_id=result.id, role_id=leader.id)
        session.add(gmr)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/member/<class_member_id:int>",
    methods=["POST"],
)
@openapi.summary("加入分组")
@openapi.tag("分组接口")
@openapi.description(
    """申请加入一个分组，或者组长邀请特定成员加入分组，或者教师将特定成员加入分组。
- 若是自行申请加入分组，则class_member_id必须为当前用户在班级中的id；
- 若是组长邀请特定成员加入分组，则class_member_id必须为被邀请成员在班级中的id。
- 若用户已经在一个组中，则无法加入新组；若用户先前申请了加入组，或者被邀请加入组，则再次申请时，
无法被邀请加入，但是本人的申请可以覆盖之前的邀请。"""
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
@need_login()
async def join_group(request, class_id: int, group_id: int, class_member_id: int):
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
            "Class is not in group status",
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

        # 获取目标班级成员
        class_member_stmt = select(ClassMember).where(
            ClassMember.class_id == class_id,
            ClassMember.id == class_member_id,
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

        # 判断这个小组是否已经满员（满员条件：小组成员数量 >= 小组角色数量，值得注意的是，小组成员数量包括未审核的成员）
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
                # 如果这个组员已经有被邀请的记录（不管是自己组还是别人组），都不允许再次邀请
                if (
                    class_member.group_id is not None
                    and class_member.status is not None
                ):
                    return ErrorResponse.new_error(
                        400,
                        "Class Member already being invited",
                    )
                request_status = GroupMemberRoleStatus.member_review
            else:  # 自行申请，可以覆盖之前的邀请
                # 自行申请的情况下，class_member_id必须为当前用户在班级中的id
                if class_member.user.id != request.ctx.user.id:
                    return ErrorResponse.new_error(
                        400,
                        "Class Member id is invalid",
                    )
                request_status = GroupMemberRoleStatus.leader_review
        elif (
            request.ctx.user.user_type == UserType.teacher
            or request.ctx.user.user_type == UserType.admin
        ):  # 教师或管理员将特定成员加入分组
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


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/member/<class_member_id:int>",
    methods=["DELETE"],
)
@openapi.summary("退出分组")
@openapi.tag("分组接口")
@openapi.description(
    """退出一个分组，或者组长将特定成员移出分组，或者教师将特定成员移出分组。
若用户已经在一个组中，则无法退出；若用户先前申请了加入组，或者被邀请加入组，则退出时，将会取消之前的申请。"""
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
@need_login()
async def leave_group(request, class_id: int, group_id: int, class_member_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    # 判断班级是否处于分组状态
    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            403,
            "Class is not in group status",
        )

    with db() as session:
        group = session.execute(
            select(Group).where(Group.id == group_id, Group.class_id == class_id)
        ).scalar()
        # 判断分组是否存在
        if not group:
            return ErrorResponse.new_error(
                404,
                "Group Not Found",
            )
        # 判断分组是否处于待审核状态
        if group.status != GroupStatus.pending:
            return ErrorResponse.new_error(
                403,
                "Group is not in pending status",
            )

        # 获取自己的班级成员信息
        self_class_member = session.execute(
            select(ClassMember).where(
                ClassMember.class_id == class_id,
                ClassMember.group_id == group_id,
                ClassMember.user_id == request.ctx.user.id,
                ClassMember.status == GroupMemberRoleStatus.approved,
            )
        ).scalar()

        # 获取目标班级成员信息
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
            # 如果是学生，需要判断是否有权限退出
            if not self_class_member:
                return ErrorResponse.new_error(
                    403,
                    "You are not in this group",
                )
            # 判断是否是组长
            is_leader = False
            for role in self_class_member.roles:
                if role.is_manager:
                    is_leader = True
                    break
            # 如果不是组长，只能退出自己
            if self_class_member.id != class_member_id and not is_leader:
                return ErrorResponse.new_error(
                    403,
                    "You can only leave yourself",
                )
            # 如果是组长，不能退出自己
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

        # 删除组员角色
        stmt = GroupMemberRole.__table__.delete().where(
            GroupMemberRole.class_member_id == class_member_id,
        )
        session.execute(stmt)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/member/<class_member_id:int>/approve",
    methods=["POST"],
)
@openapi.summary("同意成员加入分组")
@openapi.tag("分组接口")
@openapi.description(
    """同意特定成员加入分组，该接口可以由学生、教师、管理员调用。
在由学生调用时，分为以下两种情况：
- 若是已经在组内的组长调用，则可以同意一个分组状态为`GroupMemberRoleStatus.leader_review`的成员加入分组；
- 若是尚未加入组的学生调用，则该学生需要满足自己的分组状态为`GroupMemberRoleStatus.member_review`，且该学生的`group_id`为目标分组的`id`。
在由教师或管理员调用时，则无需上述校验，可以直接将特定成员加入分组。"""
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
@need_login()
async def approve_group_member(
    request, class_id: int, group_id: int, class_member_id: int
):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    # 判断班级是否处于分组状态
    if clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            403,
            "Class is not in group status",
        )

    with db() as session:
        group = session.execute(
            select(Group).where(Group.id == group_id, Group.class_id == class_id)
        ).scalar()
        # 判断分组是否存在
        if not group:
            return ErrorResponse.new_error(
                404,
                "Group Not Found",
            )

        # 判断该分组是否处于待审核状态
        if group.status != GroupStatus.pending:
            return ErrorResponse.new_error(
                403,
                "Group is not in pending status",
            )

        # 获取目标班级成员信息
        class_member = session.execute(
            select(ClassMember).where(
                ClassMember.class_id == class_id,
                ClassMember.group_id == group_id,
                ClassMember.id == class_member_id,
            )
        ).scalar()
        # 判断目标成员是否在分组中
        if not class_member:
            return ErrorResponse.new_error(
                404,
                "The specified member is not in the group",
            )

        # 获取自己的班级成员信息
        self_class_member = session.execute(
            select(ClassMember).where(
                ClassMember.class_id == class_id,
                ClassMember.group_id == group_id,
                ClassMember.user_id == request.ctx.user.id,
                ClassMember.status == GroupMemberRoleStatus.approved,
            )
        ).scalar()

        # 判断用户是否有权限同意特定成员加入分组
        if request.ctx.user.user_type == UserType.student:
            # 如果是学生，需要判断是否有权限同意
            if not self_class_member:
                return ErrorResponse.new_error(
                    403,
                    "You are not in this group",
                )
            # 判断是否是组长
            is_leader = False
            for role in self_class_member.roles:
                if role.is_manager:
                    is_leader = True
                    break
            # 如果不是组长，且不是组长邀请自己加入的，无法同意
            if (
                not is_leader
                and class_member.status == GroupMemberRoleStatus.leader_review
            ):
                return ErrorResponse.new_error(
                    403,
                    "You cannot approve this member",
                )
            # 如果是组长邀请其他成员加入的，只有那个成员可以同意
            elif (
                class_member.status == GroupMemberRoleStatus.member_review
                and class_member.id != self_class_member.id
            ):
                return ErrorResponse.new_error(
                    403,
                    "You cannot approve this member",
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
            .values(status=GroupMemberRoleStatus.approved)
        )
        session.execute(stmt)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/member/<class_member_id:int>",
    methods=["GET"],
)
@openapi.summary("查询分组成员信息")
@openapi.tag("分组接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[ClassMemberSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_group_member(request, class_id: int, group_id: int, class_member_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(404, "Group not found.")

    with db() as session:
        class_member = session.execute(
            select(ClassMember).where(
                ClassMember.group_id == group_id,
                ClassMember.class_id == class_id,
                ClassMember.id == class_member_id,
            )
        ).scalar()

        if not class_member:
            return ErrorResponse.new_error(404, "Group member not found.")

        return BaseDataResponse(
            data=ClassMemberSchema.model_validate(class_member)
        ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/member/<class_member_id:int>",
    methods=["PUT"],
)
@openapi.summary("修改分组成员信息")
@openapi.tag("分组接口")
@openapi.description(
    """
修改分组成员信息，可修改以下内容：
- 组员的 Git 仓库账号，传入一个列表，每一个元素都是 String 类型；
- 组员的角色ID，传入列表，每一个元素都是整数类型，表示角色ID，必须是该班级的角色，同时，已有的组长角色不可修改；每个角色在一个组内只能有一个人；

仅组长可以修改组员信息，组员必须是已经加入组的组员。
"""
)
@openapi.body(
    {
        "application/json": UpdateGroupMemberRequest.schema(
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
@need_login()
@validate(json=UpdateGroupMemberRequest)
async def update_group_member(
    request,
    class_id: int,
    group_id: int,
    class_member_id: int,
    body: UpdateGroupMemberRequest,
):
    db = request.app.ctx.db

    if body.repo_usernames is None and body.role_list is None:
        return ErrorResponse.new_error(400, "No data to update.")

    body.role_list = list(set(body.role_list)) if body.role_list is not None else None

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")
    if not is_manager:
        return ErrorResponse.new_error(403, "You are not the leader of this group.")

    with db() as session:
        # 绑定 group 至该 session
        session.add(group)

        # 获取组员信息
        class_member = session.execute(
            select(ClassMember).where(
                ClassMember.group_id == group_id,
                ClassMember.class_id == class_id,
                ClassMember.id == class_member_id,
                ClassMember.status == GroupMemberRoleStatus.approved,
            )
        ).scalar()
        if not class_member:
            return ErrorResponse.new_error(404, "Group member not found.")

        # 更新组员的 Git 仓库账号
        if body.repo_usernames is not None:
            class_member.repo_usernames = body.repo_usernames

        if body.role_list is not None:
            # 获取班级角色
            class_role_id = (
                session.execute(
                    select(GroupRole.id).where(GroupRole.class_id == class_id)
                )
                .scalars()
                .all()
            )
            class_role_leader_ids = (
                session.execute(
                    select(GroupRole.id).where(
                        GroupRole.class_id == class_id, GroupRole.is_manager.is_(True)
                    )
                )
                .scalars()
                .all()
            )

            # 确保传入的角色ID是合法的
            for role_id in body.role_list:
                if role_id not in class_role_id:
                    return ErrorResponse.new_error(400, "Role ID is invalid.")

            # 更新组员的角色ID
            ori_role_ids = [role.id for role in class_member.roles]
            ori_role_group_leader_ids = [
                role_id for role_id in ori_role_ids if role_id in class_role_leader_ids
            ]
            new_role_ids = body.role_list
            new_role_group_leader_ids = [
                role_id for role_id in new_role_ids if role_id in class_role_leader_ids
            ]

            # 组长角色不可修改
            if set(ori_role_group_leader_ids) != set(new_role_group_leader_ids):
                return ErrorResponse.new_error(
                    400, "Group leader role cannot be changed."
                )

            # 获取其他该组成员的角色ID
            other_members = [
                member for member in group.members if member.id != class_member_id
            ]
            other_role_ids = []
            for member in other_members:
                other_role_ids.extend([role.id for role in member.roles])

            # 检查是否存在与其他组员角色冲突
            if set(new_role_ids) & set(other_role_ids):
                return ErrorResponse.new_error(
                    400, "Role ID conflict with other members."
                )

            # 更新组员角色
            stmt = GroupMemberRole.__table__.delete().where(
                GroupMemberRole.class_member_id == class_member_id
            )
            session.execute(stmt)

            for role_id in new_role_ids:
                stmt = GroupMemberRole(
                    class_member_id=class_member_id,
                    role_id=role_id,
                )
                session.add(stmt)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>",
    methods=["GET"],
)
@openapi.summary("查询分组信息")
@openapi.tag("分组接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[GroupSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_group(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")

    with db() as session:
        session.add(group)
        return BaseDataResponse(
            data=GroupSchema.model_validate(group),
        ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>",
    methods=["PUT"],
)
@openapi.summary("修改分组信息")
@openapi.tag("分组接口")
@openapi.description(
    """
修改分组信息，可修改以下内容：
- 分组名称；

仅组长和教师可以修改分组信息。
"""
)
@openapi.body(
    {
        "application/json": UpdateGroupRequest.schema(
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
@need_login()
@validate(json=UpdateGroupRequest)
async def update_group(request, class_id: int, group_id: int, body: UpdateGroupRequest):
    db = request.app.ctx.db

    if body.group_name is None:
        return ErrorResponse.new_error(400, "No data to update.")

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")
    if not is_manager:
        return ErrorResponse.new_error(403, "You are not the leader of this group.")

    with db() as session:
        session.add(group)
        group.name = body.group_name
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>",
    methods=["DELETE"],
)
@openapi.summary("解散分组")
@openapi.tag("分组接口")
@openapi.description(
    """
解散一个分组，只有组长可以解散分组，解散分组后，所有的组内角色信息将会清空，但不会清空Git仓库账号信息。
- 只有在班级状态为`ClassStatus.grouping`时，才可以解散分组；
- 只有在分组状态为`GroupStatus.pending`时，才可以解散分组。
"""
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
@need_login()
async def delete_group(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")
    if not is_manager:
        return ErrorResponse.new_error(403, "You are not the leader of this group.")
    if group.status != GroupStatus.pending:
        return ErrorResponse.new_error(403, "Group is not in pending status.")

    with db() as session:
        session.add(group)
        if group.clazz.status != ClassStatus.grouping:
            return ErrorResponse.new_error(403, "Class is not in grouping status.")

        # 获取组员信息
        class_members = (
            session.execute(
                select(ClassMember).where(
                    ClassMember.group_id == group_id,
                    ClassMember.class_id == class_id,
                )
            )
            .scalars()
            .all()
        )

        # 删除组员角色
        stmt = GroupMemberRole.__table__.delete().where(
            GroupMemberRole.class_member_id.in_([member.id for member in class_members])
        )
        session.execute(stmt)

        # 删除组员信息
        stmt = (
            ClassMember.__table__.update()
            .where(ClassMember.group_id == group_id)
            .values(group_id=None, status=None)
        )
        session.execute(stmt)

        # 删除组信息
        stmt = Group.__table__.delete().where(Group.id == group_id)
        session.execute(stmt)

        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/approve",
    methods=["POST"],
)
@openapi.summary("审核分组")
@openapi.tag("分组接口")
@openapi.description(
    """
审核分组，只有教师可以审核分组，审核分组后，分组状态将会变为`GroupStatus.normal`。
- 只有在班级状态为`ClassStatus.grouping`时，才可以审核分组；
- 只有在分组状态为`GroupStatus.pending`时，才可以审核分组。
- 分组审核后，该组将无法新增或删除成员，但可以修改成员的信息。
"""
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
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def approve_group(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")
    if group.status != GroupStatus.pending:
        return ErrorResponse.new_error(403, "Group is not in pending status.")

    with db() as session:
        session.add(group)
        if group.clazz.status != ClassStatus.grouping:
            return ErrorResponse.new_error(403, "Class is not in grouping status.")

        group.status = GroupStatus.normal
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()


@group_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/approve",
    methods=["DELETE"],
)
@openapi.summary("撤销分组审核")
@openapi.tag("分组接口")
@openapi.description(
    """
撤销分组审核，只有教师可以撤销分组审核，撤销分组审核后，分组状态将会变为`GroupStatus.pending`。
- 只有在班级状态为`ClassStatus.grouping`时，才可以撤销分组审核；
- 只有在分组状态为`GroupStatus.normal`时，才可以撤销分组审核。
"""
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
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def revoke_group_approval(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    # 判断用户是否有班级访问权限
    group, self_class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )

    if not group:
        return ErrorResponse.new_error(404, "Group not found.")
    if group.status != GroupStatus.normal:
        return ErrorResponse.new_error(403, "Group is not in normal status.")

    with db() as session:
        session.add(group)
        if group.clazz.status != ClassStatus.grouping:
            return ErrorResponse.new_error(403, "Class is not in grouping status.")

        group.status = GroupStatus.pending
        session.commit()

    return BaseDataResponse(
        data=None,
    ).json_response()
