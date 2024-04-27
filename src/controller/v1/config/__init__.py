from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select

from controller.v1.config.request_model import UpdateConfigRequestModel
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Config
from model.enum import UserType
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    ErrorResponse,
)
from model.schema import ConfigSchema

config_bp = Blueprint("config", url_prefix="/config")


@config_bp.route("/list", methods=["GET"])
@openapi.summary("获取配置列表")
@openapi.tag("配置接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[ConfigSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin])
async def get_config_list(request):
    db = request.app.ctx.db

    stmt = select(Config).order_by(Config.id)

    with db() as session:
        result = session.execute(stmt).scalars().all()
        return BaseListResponse(
            data=[ConfigSchema.model_validate(item) for item in result],
            total=len(result),
            page=1,
            page_size=len(result),
        ).json_response()


@config_bp.route("/site_config", methods=["GET"])
@openapi.summary("获取站点配置")
@openapi.tag("配置接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
async def get_site_config(request):
    db = request.app.ctx.db
    config_list = ["course:title"]

    stmt = select(Config).where(Config.key.in_(config_list))

    with db() as session:
        result = session.execute(stmt).scalars().all()
        return BaseDataResponse(
            data={item.key: item.value for item in result}
        ).json_response()


@config_bp.route("/<config_id:str>", methods=["PUT"])
@openapi.summary("修改配置")
@openapi.tag("配置接口")
@openapi.body(
    {
        "application/json": UpdateConfigRequestModel.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[ConfigSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin])
@validate(json=UpdateConfigRequestModel)
async def update_config(request, config_id, body: UpdateConfigRequestModel):
    db = request.app.ctx.db

    stmt = select(Config).where(Config.key == config_id)

    with db() as session:
        config = session.execute(stmt).scalar()
        if not config:
            return ErrorResponse.new_error(404, "Config not found")

        config.value = body.value
        session.commit()

        request.app.ctx.log.add_log(
            "config:update_config",
            f"Update config {config.key}",
            request,
        )

        return BaseDataResponse(
            data=ConfigSchema.model_validate(config)
        ).json_response()
