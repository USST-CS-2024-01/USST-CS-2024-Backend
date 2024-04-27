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
from model.enum import UserType, ClassStatus
from model.response_model import (
    BaseDataResponse,
    BaseListResponse,
    ErrorResponse,
)
from model.schema import UserSchema, ClassMemberSchema
from util.parameter import generate_parameters_from_pydantic

class_bp = Blueprint("class", url_prefix="/class")


@class_bp.route("/list", methods=["GET"])
@openapi.summary("获取班级列表")
@openapi.tag("班级接口")
@openapi.definition(parameter=generate_parameters_from_pydantic(ListClassRequest))
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[ClassReturnItem].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@validate(query=ListClassRequest)
@need_login()
async def get_class_list(request, query: ListClassRequest):
    db = request.app.ctx.db

    # 选择班级信息，包含成员数量、教师列表
    stmt = select(Class).where(
        or_(
            Class.members.any(id=request.ctx.user.id),
            request.ctx.user.user_type == UserType.admin,
        )
    )

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
    count_stmt = select(func.count()).select_from(stmt.subquery())
    stmt = stmt.offset(query.offset).limit(query.limit)
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
@openapi.body(
    {
        "application/json": ChangeClassInfoRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[ClassReturnItem].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin])
@validate(json=ChangeClassInfoRequest)
async def create_class(request, body: ChangeClassInfoRequest):
    db = request.app.ctx.db

    try:
        new_class = service.class_.generate_new_class(db, body.name, body.description)
    except Exception as e:
        return ErrorResponse.new_error(
            400,
            str(e),
        )

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:create_class",
        content=f"Create class {new_class.name}({new_class.id})",
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
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[ClassReturnItem].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_class_info(request, class_id: int):
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
            .filter(ClassMember.class_id == class_id, ClassMember.is_teacher.is_(False))
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
@openapi.body(
    {
        "application/json": ChangeClassInfoRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[ClassReturnItem].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=ChangeClassInfoRequest)
async def update_class_info(request, class_id: int, body: ChangeClassInfoRequest):
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

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:update_class_info",
        content=f"Update class {clazz.name}({clazz.id})",
    )

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
@openapi.description("删除班级，不可恢复，这是一个危险操作，建议在前端进行二次确认")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin])
async def delete_class(request, class_id: int):
    db = request.app.ctx.db

    if not service.class_.has_class_access(request, class_id):
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )

    with db() as session:
        session.execute(Class.__table__.delete().where(Class.id == class_id))
        session.commit()

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:delete_class",
        content=f"Delete class {class_id}",
    )

    return BaseDataResponse.new_data({})


@class_bp.route("/<class_id:int>/member", methods=["GET"])
@openapi.summary("获取班级成员")
@openapi.tag("班级接口")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[ClassMemberSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
async def get_class_member(request, class_id: int):
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
        result = [ClassMemberSchema.model_validate(x) for x in result]

    return BaseListResponse(
        data=result, page=1, page_size=len(result), total=len(result)
    ).json_response()


@class_bp.route("/<class_id:int>/member", methods=["POST"])
@openapi.summary("批量添加班级成员")
@openapi.tag("班级接口")
@openapi.description(
    """
批量添加班级成员，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.not_started`或者`ClassStatus.grouping`时，才能添加成员。
- 一旦班级状态变更为更后续状态，将无法对成员进行修改。
"""
)
@openapi.body(
    {
        "application/json": AddClassMemberRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": ClassMemberOperationResult.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=AddClassMemberRequest)
async def add_class_member(request, class_id: int, body: AddClassMemberRequest):
    db = request.app.ctx.db

    if class_id == 1:
        return ErrorResponse.new_error(
            400,
            "Can not modify the default class",
        )

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.not_started and clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            400,
            "Only can add member when class status is not_started or grouping",
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

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:add_class_member",
        content=f"Add member to class {class_id}",
    )

    result.failed_list = [int(x) for x in result.failed_list]

    return result.json_response()


@class_bp.route("/<class_id:int>/member", methods=["DELETE"])
@openapi.summary("批量删除班级成员")
@openapi.tag("班级接口")
@openapi.description(
    """
批量删除班级成员，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.not_started`或者`ClassStatus.grouping`时，才能删除成员。
- 一旦班级状态变更为更后续状态，将无法对成员进行修改。
"""
)
@openapi.body(
    {
        "application/json": RemoveClassMemberRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": ClassMemberOperationResult.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(json=RemoveClassMemberRequest)
async def remove_class_member(request, class_id: int, body: RemoveClassMemberRequest):
    db = request.app.ctx.db

    if class_id == 1:
        return ErrorResponse.new_error(
            400,
            "Can not modify the default class",
        )

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.not_started and clazz.status != ClassStatus.grouping:
        return ErrorResponse.new_error(
            400,
            "Only can remove member when class status is not_started or grouping",
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
            member_id_list = member_id_list.where(ClassMember.is_teacher.is_(False))

        member_id_list = session.execute(member_id_list).scalars().all()
        member_id_list = [x for x in member_id_list]

        result.failed_list = list(set(body.user_id_list) - set(member_id_list))
        result.failed_count = len(result.failed_list)

        session.execute(
            ClassMember.__table__.delete().where(ClassMember.id.in_(member_id_list))
        )
        session.commit()

        result.success_count = len(member_id_list)

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:remove_class_member",
        content=f"Remove member from class {class_id}",
    )

    return result.json_response()


@class_bp.route("/<class_id:int>/archive", methods=["POST"])
@openapi.summary("归档班级")
@openapi.tag("班级接口")
@openapi.description(
    """
归档班级，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.teaching`时，才能归档班级。
- 一旦班级状态变更为`ClassStatus.archived`，将无法对班级进行修改。
- 归档班级后，小组内的任务只可以查看，不可以再提交。
"""
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def archive_class(request, class_id: int):
    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.teaching:
        return ErrorResponse.new_error(
            400,
            "Only can archive class when class status is teaching",
        )

    with db() as session:
        session.execute(
            Class.__table__.update()
            .where(Class.id == class_id)
            .values(status=ClassStatus.finished)
        )
        session.commit()

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:archive_class",
        content=f"Archive class {class_id}",
    )

    return BaseDataResponse.new_data({})


@class_bp.route("/<class_id:int>/archive", methods=["DELETE"])
@openapi.summary("取消归档班级")
@openapi.tag("班级接口")
@openapi.description(
    """
取消归档班级，需要管理员或教师权限。
- 仅当班级状态为`ClassStatus.archived`时，才能取消归档班级。
- 取消归档班级操作的目标班级状态为`ClassStatus.teaching`。
"""
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse.schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def unarchive_class(request, class_id: int):
    db = request.app.ctx.db

    clazz = service.class_.has_class_access(request, class_id)
    if not clazz:
        return ErrorResponse.new_error(
            404,
            "Class Not Found",
        )
    if clazz.status != ClassStatus.finished:
        return ErrorResponse.new_error(
            400,
            "Only can unarchive class when class status is archived",
        )

    with db() as session:
        session.execute(
            Class.__table__.update()
            .where(Class.id == class_id)
            .values(status=ClassStatus.teaching)
        )
        session.commit()

    request.app.ctx.log.add_log(
        request=request,
        log_type="class:unarchive_class",
        content=f"Unarchive class {class_id}",
    )

    return BaseDataResponse.new_data({})
