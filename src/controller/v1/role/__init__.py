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

from controller.v1.class_.request_model import ListClassRequest
from controller.v1.class_.response_model import ClassReturnItem
from controller.v1.role.request_model import CreateGroupRoleRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Class, ClassMember, GroupRole
from model.enum import UserType
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
@need_login()
def get_role_list(request, class_id: int):
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
            data=[GroupRoleSchema.from_orm(item) for item in result],
            total=len(result),
            page=1,
            page_size=len(result),
        ).json_response()


@role_bp.route("/class/<class_id:int>/role/create", methods=["POST"])
@openapi.summary("创建班级角色")
@openapi.tag("角色接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=CreateGroupRoleRequest)
def create_class_role(request, class_id: int, body: CreateGroupRoleRequest):
    db = request.app.ctx.db

    if not has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
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
        new_role_pydantic = GroupRoleSchema.from_orm(new_role)

    return BaseDataResponse(
        code=200,
        message="ok",
        data=new_role_pydantic,
    ).json_response()
