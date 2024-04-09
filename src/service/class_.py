from sqlalchemy import select, and_, or_

from model import Class, UserType


def has_class_access(request, class_id: int) -> bool:
    """
    Check whether the user has access to the class
    :param request: Request
    :param class_id: Class ID
    :return: Whether the user has access to the class
    """
    user = request.ctx.user
    db = request.app.ctx.db
    stmt = select(Class).where(
        and_(
            Class.id == class_id,
            or_(
                Class.members.any(id=user.id),
                user.user_type == UserType.admin,
            ),
        )
    )

    with db() as session:
        result = session.execute(stmt)
        return result.scalar() is not None
