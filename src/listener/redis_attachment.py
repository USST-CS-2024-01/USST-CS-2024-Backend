from sanic import Sanic
from sanic.log import logger

from model import RedisClient

TIMINGS = ["before_server_start"]


async def before_server_start(app: Sanic) -> None:
    """
    Attach redis into Sanic App
    :param app: Sanic App
    :return: None
    """

    host = app.config.REDIS_HOST
    port = app.config.REDIS_PORT
    password = app.config.REDIS_PASSWORD
    database = app.config.REDIS_DB

    app.ctx.cache = RedisClient(host, port, database, password)

    logger.info("Redis attached.")
