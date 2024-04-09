from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, func, select, or_

from controller.v1.class_.request_model import ListClassRequest
from controller.v1.class_.response_model import ClassReturnItem
from middleware.auth import need_login
from middleware.validator import validate
from model import Class, ClassMember
from model.enum import UserType
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    BaseResponse,
    ErrorResponse,
)
from model.schema import ClassSchema

class_bp = Blueprint("class", url_prefix="/class")


@class_bp.route("/list", methods=["GET"])
@openapi.summary("获取班级列表")
@openapi.tag("班级接口")
@validate(query=ListClassRequest)
@need_login()
def get_class_list(request, query: ListClassRequest):
    db = request.app.ctx.db

    # 选择班级信息，包含成员数量、教师列表
    stmt = (
        select(Class)
        .where(
            or_(
                Class.members.any(id=request.ctx.user.id),
                request.ctx.user.user_type == UserType.admin,
            )
        )
        .offset(query.offset)
        .limit(query.limit)
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())

    if query.status:
        stmt = stmt.where(Class.status == query.status)
    if query.kw:
        stmt = stmt.where(Class.name.like(f"%{query.kw}%"))
    if query.user_id:
        stmt = stmt.where(Class.members.any(id=query.user_id))

    if query.order_by:
        stmt = stmt.order_by(
            # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
            getattr(getattr(Class, query.order_by), query.asc and "asc" or "desc")()
        )

    result_list = []

    with db() as session:
        result = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar()
        for item in result:
            stu_count = (
                session.query(ClassMember)
                .filter(
                    ClassMember.is_teacher == False, ClassMember.class_id == item.id
                )
                .count()
            )
            tea_list = (
                session.query(ClassMember)
                .filter(ClassMember.is_teacher == True, ClassMember.class_id == item.id)
                .limit(3)
                .all()
            )
            result_list.append(
                ClassReturnItem(
                    id=item.id,
                    name=item.name,
                    status=item.status,
                    stu_count=stu_count,
                    tea_list=tea_list,
                )
            )

    return BaseListResponse(
        data=result_list, page=query.page, page_size=query.page_size, total=total
    ).json_response()


@class_bp.route("/<class_id:int>", methods=["GET"])
@openapi.summary("获取班级信息")
@openapi.tag("班级接口")
@need_login()
def get_class_info(request, class_id: int):
    db = request.app.ctx.db

    stmt = select(Class).where(
        and_(
            Class.id == class_id,
            or_(
                Class.members.any(id=request.ctx.user.id),
                request.ctx.user.user_type == UserType.admin,
            ),
        )
    )

    with db() as session:
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            return ErrorResponse.new_error(
                404,
                "Class Not Found",
            )

        stu_list = (
            session.query(ClassMember)
            .filter(ClassMember.class_id == class_id, ClassMember.is_teacher == False)
            .all()
        )
        stu_count = len(stu_list)
        tea_list = (
            session.query(ClassMember)
            .filter(ClassMember.is_teacher == True, ClassMember.class_id == class_id)
            .all()
        )

    return BaseDataResponse.new_data(
        ClassReturnItem(
            id=result.id,
            name=result.name,
            description=result.description,
            status=result.status,
            stu_count=stu_count,
            tea_list=tea_list,
            stu_list=stu_list,
            first_task_id=result.first_task_id,
        )
    )
