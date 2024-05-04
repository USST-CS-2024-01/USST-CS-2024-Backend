import hashlib
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


async def get_avatar_url(request, user_id: int) -> str:
    """
    Get avatar URL
    :param request: Request
    :param user_id: User ID
    :return: Avatar URL
    """

    cache = request.app.ctx.cache
    db = request.app.ctx.db

    cache_key = f"user_avatar:{user_id}"
    avatar_url = await cache.get(cache_key)
    if avatar_url:
        return avatar_url.decode()

    user = get_user(db, user_id=user_id)
    if not user:
        user_email = ""
    else:
        user_email = user.email

    email_sha = hashlib.sha256(user_email.encode()).hexdigest()
    avatar_url = f"https://sdn.geekzu.org/avatar/{email_sha}?d=identicon"

    await cache.set(cache_key, avatar_url, expire=3600)
    return avatar_url
