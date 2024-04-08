from functools import wraps
from inspect import isawaitable
from typing import Optional, Union, Callable, Type, TypeVar
from urllib.request import Request

from sanic_ext.exceptions import InitError
from sanic_ext.extras.validation.setup import generate_schema, do_validation
from sanic_ext.utils.extraction import extract_request

from model.response_model import ErrorResponse

T = TypeVar("T")


def validate(
    json: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    form: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    query: Optional[Union[Callable[[Request], bool], Type[object]]] = None,
    body_argument: str = "body",
    query_argument: str = "query",
) -> Callable[[T], T]:
    schemas = {
        key: generate_schema(param)
        for key, param in (
            ("json", json),
            ("form", form),
            ("query", query),
        )
    }

    if json and form:
        raise InitError("Cannot define both a form and json route validator")

    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            request = extract_request(*args)

            schema = None
            if schemas["json"]:
                schema = schemas["json"]
            elif schemas["form"]:
                schema = schemas["form"]
            elif schemas["query"]:
                schema = schemas["query"]

            try:
                await do_validation(
                    model=json,
                    data=request.json,
                    schema=schema,
                    request=request,
                    kwargs=kwargs,
                    body_argument=body_argument,
                    allow_multiple=False,
                    allow_coerce=False,
                )
            except Exception as e:
                return ErrorResponse.new_error(
                    code=400, message="Bad Request", detail=str(e)
                )

            retval = f(*args, **kwargs)
            if isawaitable(retval):
                retval = await retval
            return retval

        return decorated_function

    return decorator
