# _*_ coding: utf-8 _*_
"""
Time:     2024/4/9 15:13
Author:   不做评论(vvbbnn00)
Version:  
File:     __init__.py.py
Describe: 
"""
from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, func, select, or_

from controller.v1.role.request_model import CreateGroupRoleRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Class, ClassMember, GroupRole
from model.enum import UserType, ClassStatus
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    BaseResponse,
    ErrorResponse,
)
from model.schema import ClassSchema, GroupRoleSchema
from service.class_ import has_class_access

role_bp = Blueprint("role")


@role_bp.route("/class/<class_id:int>/role/list", methods=["GET"])
@openapi.summary("获取班级角色列表")
@openapi.tag("角色接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[GroupRoleSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_role_list(request, class_id: int):
    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    stmt = select(GroupRole).where(GroupRole.class_id == class_id)

    with db() as session:
        result = session.execute(stmt).scalars().all()
        return BaseListResponse(
            data=[GroupRoleSchema.model_validate(item) for item in result],
            total=len(result),
            page=1,
            page_size=len(result),
        ).json_response()


@role_bp.route("/class/<class_id:int>/role/create", methods=["POST"])
@openapi.summary("创建班级角色")
@openapi.tag("角色接口")
@openapi.description(
    """
创建班级角色，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.not_started`时，才能创建角色。
- 一旦班级状态变更为更后续状态，将无法对角色进行修改。
"""
)
@openapi.body(
    {
        "application/json": CreateGroupRoleRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[GroupRoleSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=CreateGroupRoleRequest)
async def create_class_role(request, class_id: int, body: CreateGroupRoleRequest):
    db = request.app.ctx.db

    clazz = has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.not_started:
        return ErrorResponse.new_error(
            400,
            "Role can only be created when class status is not_started",
        )

    insert_dict = body.dict()

    # 创建一个新的 GroupRole 对象
    new_role = GroupRole(**insert_dict)
    new_role.class_id = class_id

    new_role_pydantic: GroupRoleSchema

    with db() as sess:
        # 添加到会话并提交，这将自动填充 new_user 的 id 属性
        sess.add(new_role)
        sess.commit()
        # 刷新对象，以获取数据库中的所有字段
        sess.refresh(new_role)
        new_role_pydantic = GroupRoleSchema.model_validate(new_role)

    return BaseDataResponse(
        code=200,
        message="ok",
        data=new_role_pydantic,
    ).json_response()


@role_bp.route("/class/<class_id:int>/role/<role_id:int>", methods=["PUT"])
@openapi.summary("修改班级角色")
@openapi.tag("角色接口")
@openapi.description(
    """
修改班级角色，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.not_started`时，才能修改角色。
- 一旦班级状态变更为更后续状态，将无法对角色进行修改。
"""
)
@openapi.body(
    {
        "application/json": CreateGroupRoleRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[GroupRoleSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=CreateGroupRoleRequest)
async def update_class_role(
    request, class_id: int, role_id: int, body: CreateGroupRoleRequest
):
    db = request.app.ctx.db

    clazz = has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.not_started:
        return ErrorResponse.new_error(
            400,
            "Role can only be updated when class status is not_started",
        )

    insert_dict = body.model_dump(exclude_unset=True)
    if not insert_dict:
        return ErrorResponse.new_error(
            400,
            "No data to update",
        )

    with db() as sess:
        stmt = select(GroupRole).where(
            and_(GroupRole.class_id == class_id, GroupRole.id == role_id)
        )
        role = sess.execute(stmt).scalar_one_or_none()
        if not role:
            return ErrorResponse.new_error(
                404,
                "Role Not Found",
            )

        for key, value in insert_dict.items():
            setattr(role, key, value)

        sess.commit()
        sess.refresh(role)
        role_pydantic = GroupRoleSchema.model_validate(role)

    return BaseDataResponse(
        code=200,
        message="ok",
        data=role_pydantic,
    ).json_response()


@role_bp.route("/class/<class_id:int>/role/<role_id:int>", methods=["DELETE"])
@openapi.summary("删除班级角色")
@openapi.tag("角色接口")
@openapi.description(
    """
删除班级角色，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.not_started`时，才能删除角色。
- 一旦班级状态变更为更后续状态，将无法对角色进行修改。
"""
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def delete_class_role(request, class_id: int, role_id: int):
    db = request.app.ctx.db

    clazz = has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.not_started:
        return ErrorResponse.new_error(
            400,
            "Role can only be deleted when class status is not_started",
        )

    with db() as sess:
        stmt = select(GroupRole).where(
            and_(GroupRole.class_id == class_id, GroupRole.id == role_id)
        )
        role = sess.execute(stmt).scalar_one_or_none()
        if not role:
            return ErrorResponse.new_error(
                404,
                "Role Not Found",
            )

        sess.delete(role)
        sess.commit()

    return BaseResponse(code=200, message="ok").json_response()
