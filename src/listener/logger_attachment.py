from sanic import Sanic
from sanic.log import logger
from util.logger import Logger

TIMINGS = ["before_server_start"]


async def before_server_start(app: Sanic) -> None:
    """
    Attach database into Sanic App
    :param app: Sanic App
    :return: None
    """

    app.ctx.log = Logger(app.ctx.db_engine)
    logger.info("Sql Logger attached.")
