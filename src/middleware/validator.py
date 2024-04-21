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

    if not any(schemas.values()):
        raise InitError("No route validator defined")

    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            request = extract_request(*args)
            try:
                if schemas["json"]:
                    await do_validation(
                        model=json,
                        data=request.json,
                        schema=schemas["json"],
                        request=request,
                        kwargs=kwargs,
                        body_argument=body_argument,
                        allow_multiple=False,
                        allow_coerce=False,
                    )
                elif schemas["form"]:
                    await do_validation(
                        model=form,
                        data=request.form,
                        schema=schemas["form"],
                        request=request,
                        kwargs=kwargs,
                        body_argument=body_argument,
                        allow_multiple=True,
                        allow_coerce=True,
                    )
                elif schemas["query"]:
                    await do_validation(
                        model=query,
                        data=request.args,
                        schema=schemas["query"],
                        request=request,
                        kwargs=kwargs,
                        body_argument=query_argument,
                        allow_multiple=True,
                        allow_coerce=True,
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

    return decorator  # type: ignore
