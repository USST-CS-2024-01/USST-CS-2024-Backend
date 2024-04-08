import asyncio
from functools import wraps
from inspect import isawaitable
from operator import and_
from typing import Callable, TypeVar

from sanic_ext.utils.extraction import extract_request
from sqlalchemy import select

from model import User, AccountStatus
from model.response_model import ErrorResponse

T = TypeVar("T")


def need_login() -> Callable[[T], T]:
    """
    Decorator to require login
    :return: Decorator
    """

    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            request = extract_request(*args)
            cache = request.app.ctx.cache

            session_id = request.headers.get("Authorization")
            if not session_id:
                return ErrorResponse.new_error(
                    code=401, message="Unauthorized", detail="Missing session ID"
                )

            if not session_id.startswith("Bearer "):
                return ErrorResponse.new_error(
                    code=401, message="Unauthorized", detail="Invalid session ID"
                )

            session_id = session_id[7:]
            user = await cache.get_pickle(session_id)
            if not user:
                return ErrorResponse.new_error(
                    code=401, message="Unauthorized", detail="Invalid session ID"
                )

            no_check = await cache.get("session_no_check:" + session_id)
            if no_check:
                request.ctx.user = user
                asyncio.create_task(cache.update_expire(session_id, 3600))
            else:
                stmt = (
                    select(User)
                    .where(
                        and_(
                            User.id == user.id,
                            User.account_status == AccountStatus.active,
                        )
                    )
                    .limit(1)
                )

                with request.app.ctx.db() as db:
                    user = db.scalar(stmt)
                if not user:
                    return ErrorResponse.new_error(
                        code=401, message="Unauthorized", detail="Invalid session ID"
                    )
                asyncio.create_task(cache.set_pickle(session_id, user, expire=3600))
                asyncio.create_task(
                    cache.set("session_no_check:" + session_id, 1, expire=60)
                )
                request.ctx.user = user
                request.ctx.session_id = session_id

            retval = f(*args, **kwargs)
            if isawaitable(retval):
                retval = await retval
            return retval

        return decorated_function

    return decorator # type: ignore
