from sanic import Sanic
from sanic.log import logger

from service.goflet import Goflet

TIMINGS = ["before_server_start"]


async def before_server_start(app: Sanic) -> None:
    """
    Attach goflet into Sanic App
    :param app: Sanic App
    :return: None
    """

    base_url = app.config.GOFLET_BASE_URL
    jwt_algorithm = app.config.GOFLET_JWT_ALGORITHM
    jwt_secret = app.config.GOFLET_JWT_SECRET
    jwt_private_key = app.config.GOFLET_JWT_PRIVATE_KEY
    jwt_issuer = app.config.GOFLET_JWT_ISSUER
    jwt_expiration = app.config.GOFLET_JWT_EXPIRATION

    app.ctx.goflet = Goflet(
        base_url,
        jwt_algorithm,
        jwt_secret,
        jwt_private_key,
        jwt_issuer,
        jwt_expiration,
    )

    logger.info("Goflet attached.")
