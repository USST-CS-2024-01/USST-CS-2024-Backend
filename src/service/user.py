from typing import Optional
from sqlalchemy import select

from model import User


def get_user(
    db,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    employee_id: Optional[str] = None,
):
    """
    Get user by ID or email
    :param db: Database session
    :param user_id: User ID
    :param email: User email
    :param username: User username
    :param employee_id: User employee ID
    :return: User
    """
    stmt = select(User)
    if user_id:
        stmt = stmt.where(User.id == user_id)
    elif email:
        stmt = stmt.where(User.email == email)
    elif username:
        stmt = stmt.where(User.username == username)
    elif employee_id:
        stmt = stmt.where(User.employee_id == employee_id)
    else:
        return None

    with db() as sess:
        user = sess.execute(stmt).scalar()

    return user
