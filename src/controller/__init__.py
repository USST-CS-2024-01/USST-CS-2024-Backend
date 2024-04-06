from sanic import Blueprint, Sanic

from .v1 import bp as v1_bp

bp = Blueprint.group(v1_bp, url_prefix="/api")


def inject_controller(app: Sanic):
    """
    Inject controller modules into a Sanic application
    :param app: Sanic application
    :return: None
    """
    app.blueprint(bp)
