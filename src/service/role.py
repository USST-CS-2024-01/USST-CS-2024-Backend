from typing import List

from model import GroupRole, ClassMember


def get_group_role_list(request, class_id: int) -> List[GroupRole]:
    """
    Get group role list by group ID
    :param request: Request
    :param class_id: Class ID
    :return: Group role list
    """
    with request.app.ctx.db() as session:
        roles = session.query(GroupRole).filter(GroupRole.class_id == class_id).all()
        return roles


def check_group_role_ids(
    request, class_id: int, role_ids: List[int]
) -> List[GroupRole]:
    """
    Check whether the role IDs are valid
    :param request: Request
    :param class_id: Class ID
    :param role_ids: Role IDs
    :return: Whether the role IDs are valid
    """
    roles = get_group_role_list(request, class_id)
    role_ids = set(role_ids)

    if not roles:
        raise ValueError("Group roles not found.")

    all_role_ids = set(role.id for role in roles)
    if not role_ids.issubset(all_role_ids):
        raise ValueError("Invalid role IDs.")

    filtered_roles = [role for role in roles if role.id in role_ids]
    return filtered_roles


def check_user_has_role(
    request, class_id: int, user_id: int, role_ids: List[int]
) -> bool:
    """
    Check whether the user has the role
    :param request: Request
    :param class_id: Class ID
    :param user_id: User ID
    :param role_ids: Role IDs
    """
    with request.app.ctx.db() as session:
        class_member = (
            session.query(ClassMember)
            .filter(
                ClassMember.class_id == class_id,
                ClassMember.user_id == user_id,
            )
            .first()
        )
        if not class_member:
            return False

        class_member_roles = set([role.id for role in class_member.roles])
        if not set(role_ids).issubset(class_member_roles):
            return False

        return True
