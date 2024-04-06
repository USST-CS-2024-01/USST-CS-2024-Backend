from sanic import Sanic
from sanic.log import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from model import Base

TIMINGS = ["before_server_start"]


def check_mysql_driver():
    """
    Try to import pymysql to check whether the mysql driver is ready
    :return:
    """
    try:
        import pymysql

        assert pymysql.__version__
    except Exception as e:
        logger.error(
            "Failed to attach mysql connection, please ensure that you have installed pymysql. (%s)",
            e,
        )


async def before_server_start(app: Sanic) -> None:
    """
    Attach database into Sanic App
    :param app: Sanic App
    :return: None
    """
    check_mysql_driver()

    host = app.config.MYSQL_HOST
    port = app.config.MYSQL_PORT
    user = app.config.MYSQL_USER
    password = app.config.MYSQL_PASSWORD
    database = app.config.MYSQL_DATABASE

    mysql_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(mysql_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    app.ctx.db = scoped_session(session_factory)

    logger.info("Mysql attached.")
