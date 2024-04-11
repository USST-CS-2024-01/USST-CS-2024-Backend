from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import and_, func, select, or_

import service.class_
from controller.v1.class_.request_model import (
    ListClassRequest,
    ChangeClassInfoRequest,
    AddClassMemberRequest,
    RemoveClassMemberRequest,
)
from controller.v1.class_.response_model import (
    ClassReturnItem,
    ClassMemberOperationResult,
)
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import Class, ClassMember, User
from model.enum import UserType
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    ErrorResponse,
)
from model.schema import UserSchema

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
            tea_list = [UserSchema.model_validate(x.user) for x in tea_list]
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


@class_bp.route("/create", methods=["POST"])
@openapi.summary("创建班级")
@openapi.tag("班级接口")
@need_login()
@need_role([UserType.admin])
@validate(json=ChangeClassInfoRequest)
def create_class(request, body: ChangeClassInfoRequest):
    db = request.app.ctx.db

    try:
        new_class = service.class_.generate_new_class(db, body.name, body.description)
    except Exception as e:
        return ErrorResponse.new_error(
            400,
            str(e),
        )

    return BaseDataResponse.new_data(
        ClassReturnItem(
            id=new_class.id,
            name=new_class.name,
            description=new_class.description,
            status=new_class.status,
        )
    )


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
            .filter(ClassMember.is_teacher is True, ClassMember.class_id == class_id)
            .all()
        )

        stu_list = [UserSchema.model_validate(x.user) for x in stu_list]
        tea_list = [UserSchema.model_validate(x.user) for x in tea_list]

    return BaseDataResponse.new_data(
        ClassReturnItem(
            id=result.id,
            name=result.name,
            description=result.description,
            status=result.status,
            stu_count=stu_count,
            tea_count=len(tea_list),
            tea_list=tea_list,
            stu_list=stu_list,
            first_task_id=result.first_task_id,
        )
    )


@class_bp.route("/<class_id:int>", methods=["PUT"])
@openapi.summary("修改班级信息")
@openapi.tag("班级接口")
@openapi.description("修改班级名称、班级描述等基本信息，不包括对班级成员、任务等的修改")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=ChangeClassInfoRequest)
def update_class_info(request, class_id: int, body: ChangeClassInfoRequest):
    db = request.app.ctx.db

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    update_dict = body.dict(exclude_unset=True)
    if not update_dict:
        return ErrorResponse.new_error(
            400,
            "No field to update",
        )

    with db() as session:
        stmt = Class.__table__.update().where(Class.id == class_id).values(update_dict)
        session.execute(stmt)
        session.commit()
        clazz = session.execute(select(Class).where(Class.id == class_id)).scalar_one()

    return BaseDataResponse.new_data(
        ClassReturnItem(
            id=clazz.id,
            name=clazz.name,
            description=clazz.description,
            status=clazz.status,
        )
    )


@class_bp.route("/<class_id:int>", methods=["DELETE"])
@openapi.summary("删除班级")
@openapi.tag("班级接口")
@need_login()
@need_role([UserType.admin])
def delete_class(request, class_id: int):
    db = request.app.ctx.db

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    with db() as session:
        session.execute(Class.__table__.delete().where(Class.id == class_id))
        session.commit()

    return BaseDataResponse.new_data({})


@class_bp.route("/<class_id:int>/member", methods=["GET"])
@openapi.summary("获取班级成员")
@openapi.tag("班级接口")
@need_login()
def get_class_member(request, class_id: int):
    db = request.app.ctx.db

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    with db() as session:
        result = (
            session.query(ClassMember).filter(ClassMember.class_id == class_id).all()
        )

    return BaseDataResponse.new_data([item.user_id for item in result])


@class_bp.route("/<class_id:int>/member", methods=["POST"])
@openapi.summary("添加班级成员")
@openapi.tag("班级接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=AddClassMemberRequest)
def add_class_member(request, class_id: int, body: AddClassMemberRequest):
    db = request.app.ctx.db

    if class_id == 1:
        return ErrorResponse.new_error(
            400,
            "Can not modify the default class",
        )

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    result = ClassMemberOperationResult(
        success_count=0,
        failed_count=0,
        failed_list=[],
    )

    add_user_list = [x for x in body.user_dict.keys()]
    with db() as session:
        filtered_user_id_list = (
            session.query(User.id).filter(User.id.in_(add_user_list)).all()
        )
        filtered_user_id_list = [str(x[0]) for x in filtered_user_id_list]

        group_member_list = (
            session.query(ClassMember).filter(ClassMember.class_id == class_id).all()
        )
        group_member_list = [str(x.user_id) for x in group_member_list]
        filtered_user_id_list = list(
            set(filtered_user_id_list) - set(group_member_list)
        )

        result.failed_list = list(set(add_user_list) - set(filtered_user_id_list))
        result.failed_count = len(result.failed_list)

        for user_id in filtered_user_id_list:
            if request.ctx.user.user_type != UserType.admin:
                if body.user_dict[user_id]:
                    result.failed_list.append(user_id)
                    result.failed_count += 1
                    continue
            member = ClassMember(
                class_id=class_id,
                user_id=int(user_id),
                is_teacher=body.user_dict[user_id],
            )
            session.add(member)
            result.success_count += 1

        session.commit()

    result.failed_list = [int(x) for x in result.failed_list]

    return result.json_response()


@class_bp.route("/<class_id:int>/member", methods=["DELETE"])
@openapi.summary("删除班级成员")
@openapi.tag("班级接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=RemoveClassMemberRequest)
def remove_class_member(request, class_id: int, body: RemoveClassMemberRequest):
    db = request.app.ctx.db

    if class_id == 1:
        return ErrorResponse.new_error(
            400,
            "Can not modify the default class",
        )

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    result = ClassMemberOperationResult(
        success_count=0,
        failed_count=0,
        failed_list=[],
    )

    with db() as session:
        member_id_list = select(ClassMember.id).where(
            and_(
                ClassMember.class_id == class_id,
                ClassMember.user_id.in_(body.user_id_list),
            )
        )
        if request.ctx.user.user_type != UserType.admin:
            member_id_list = member_id_list.where(ClassMember.is_teacher == False)

        member_id_list = session.execute(member_id_list).scalars().all()
        member_id_list = [x for x in member_id_list]

        result.failed_list = list(set(body.user_id_list) - set(member_id_list))
        result.failed_count = len(result.failed_list)

        session.execute(
            ClassMember.__table__.delete().where(ClassMember.id.in_(member_id_list))
        )
        session.commit()

        result.success_count = len(member_id_list)

    return result.json_response()
