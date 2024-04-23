import logging

from kafka import KafkaProducer
from sanic import Sanic
from sanic.log import logger

TIMINGS = ["before_server_start"]


async def before_server_start(app: Sanic) -> None:
    """
    Attach database into Sanic App
    :param app: Sanic App
    :return: None
    """
    host = app.config.KAFKA_HOST
    port = app.config.KAFKA_PORT

    app.ctx.producer = KafkaProducer(bootstrap_servers=f"{host}:{port}")
    logger.info("Kafka attached.")
