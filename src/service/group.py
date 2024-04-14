from sqlalchemy import select

from model import Group, ClassMember, GroupMemberRoleStatus, UserType
from service import class_


def have_group_access(
    request, class_id: int, group_id: int
) -> (Group or bool, ClassMember or bool, bool):
    """
    Check whether the user has access to the group, and return the group and the class member

    :param request: Request
    :param class_id: Class ID
    :param group_id: Group ID

    :return: Group; ClassMember; Whether the user is group leader
    """
    user = request.ctx.user
    db = request.app.ctx.db

    clazz = class_.has_class_access(request, class_id)
    if not clazz:
        return False, False, False

    stmt = select(Group).where(
        Group.id == group_id,
        Group.class_id == class_id,
    )

    with db() as session:
        group = session.execute(stmt).scalar()
        if not group:
            return False, False, False

        member = (
            session.query(ClassMember)
            .filter(
                ClassMember.class_id == class_id,
                ClassMember.user_id == user.id,
                ClassMember.group_id == group_id,
                ClassMember.status == GroupMemberRoleStatus.approved,
            )
            .first()
        )

        if not member and user.user_type == UserType.student:
            return False, False, False
        elif not member:
            return group, False, True

        is_manager = False
        for role in member.roles:
            if role.is_manager:
                is_manager = True
                break

        return group, member, is_manager


def have_group_access_by_id(
    request, group_id: int
) -> (Group or bool, ClassMember or bool, bool):
    """
    Check whether the user has access to the group, and return the group and the class member

    :param request: Request
    :param group_id: Group ID

    :return: Group; ClassMember; Whether the user is group leader
    """
    db = request.app.ctx.db

    stmt = select(Group).where(
        Group.id == group_id,
    )

    with db() as session:
        group = session.execute(stmt).scalar()
        if not group:
            return False, False, False

        return have_group_access(request, group.class_id, group_id)
