from ast import Dict
from inspect import Parameter
from typing import Any, List
from sanic_ext import openapi


def generate_parameters_from_pydantic(model: Any) -> List:
    """
    从 Pydantic 模型生成 OpenAPI 参数

    :param model: Pydantic 模型
    :return: OpenAPI 参数列表
    """

    parameters = []

    for key, field in model.__fields__.items():
        parameters.append(
            {
                "name": key,
                "in": "query",
                "required": field.is_required(),
                "description": field.description,
                "schema": field.annotation,
            }
        )

    return parameters
