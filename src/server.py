from email import header
from sanic import Sanic

from config import inject_config
from controller import inject_controller
from listener import inject_listener


def create_app(app_name: str, config_file: str = "config.yaml") -> Sanic:
    """
    Create a Sanic application
    :param app_name: application name
    :param config_file: configuration file
    :return: Sanic application
    """
    app = Sanic(app_name)
    inject_config(app.config, config_file=config_file)
    inject_controller(app)
    inject_listener(app)
    # Add security scheme, Authentication header is required
    app.ext.openapi.add_security_scheme(
        "session",
        type="apiKey",
        flows={
            "in": "header",
            "name": "Authorization",
            "description": "Bearer token, 需要调用登录接口获取",
        },
    )
    # Set the default response content type to application/json
    app.ext.openapi.describe(
        app_name,
        version="1.0.0",
        description="""
本文档为软件协同设计课程过程管理系统-后端API接口文档。

**文档作者**
- 陆天成(2135060620)
""",
    )

    return app
