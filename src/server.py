from sanic import Sanic

from config import inject_config


def create_app(app_name: str, config_file: str = "config.yaml") -> Sanic:
    """
    Create a Sanic application
    :param app_name: application name
    :param config_file: configuration file
    :return: Sanic application
    """
    app = Sanic(app_name)
    inject_config(app.config, config_file=config_file)
    return app
