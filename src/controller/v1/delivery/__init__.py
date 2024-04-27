from datetime import datetime

from sanic import Blueprint
from sanic_ext.extensions.openapi import openapi
from sqlalchemy import select, and_

import service.announcement
import service.class_
import service.delivery
import service.file
import service.group
from controller.v1.delivery.request_model import (
    CreateDeliveryRequest,
    AddDeliveryItemRequest,
    AcceptDeliveryRequest,
    RejectDeliveryRequest,
    ScoreDetailRequest,
)
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import (
    Delivery,
    DeliveryStatus,
    DeliveryType,
    DeliveryItem,
    RepoRecord,
    RepoRecordStatus,
    UserType,
    TeacherScore,
)
from model.response_model import (
    ErrorResponse,
    BaseListResponse,
    BaseResponse,
    BaseDataResponse,
)
from model.schema import DeliverySchema, DeliveryItemSchema, TeacherScoreSchema

delivery_bp = Blueprint("delivery")


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/list",
    methods=["GET"],
)
@openapi.summary("获取任务提交列表")
@openapi.tag("任务提交接口")
@openapi.description("""获取任务提交列表，按照提交时间倒序排列。""")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[DeliverySchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def list_delivery(request, class_id: int, group_id: int, task_id: int):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    with db() as session:
        stmt = (
            select(Delivery)
            .where(
                and_(
                    Delivery.task_id == task_id,
                    Delivery.group_id == group_id,
                )
            )
            .order_by(Delivery.delivery_time.desc())
        )

        deliveries = session.execute(stmt).scalars().all()
        return BaseListResponse(
            data=[DeliverySchema.model_validate(delivery) for delivery in deliveries]
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/check",
    methods=["GET"],
)
@openapi.summary("检查是否可以提交任务")
@openapi.tag("任务提交接口")
@openapi.description(
    """
提交任务的条件：
- 当前最新的交付物状态（不包括草稿）为空、leader_rejected、teacher_rejected，即需要重新提交
- 该小组当前存在任务
- 该班级的状态为 teaching
- 该小组对应该任务的评分已经完成
- task_id 是当前小组的任务 ID
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
async def check_delivery(request, class_id: int, group_id: int, task_id: int):
    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    try:
        service.delivery.check_can_create_delivery(
            request, task_id=task_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    return BaseResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft",
    methods=["POST"],
)
@openapi.summary("创建任务提交草稿")
@openapi.tag("任务提交接口")
@openapi.description("""创建任务提交草稿，需要提供任务提交的评论。""")
@openapi.body(
    {
        "application/json": CreateDeliveryRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[DeliverySchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@validate(json=CreateDeliveryRequest)
async def create_delivery(
    request, class_id: int, group_id: int, task_id: int, body: CreateDeliveryRequest
):
    db = request.app.ctx.db

    try:
        (
            group,
            class_member,
            is_manager,
            current_task,
        ) = service.delivery.check_can_create_draft(
            request, task_id=task_id, class_id=class_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    try:
        draft = service.delivery.get_task_draft(request, task_id, group_id)
        if draft:
            return ErrorResponse.new_error(
                code=403, message="You already have a draft for this task."
            )
    except ValueError as e:
        pass

    with db() as session:
        delivery = Delivery(
            task_id=task_id,
            group_id=group_id,
            delivery_user=request.ctx.user.id,
            delivery_time=datetime.now(),
            delivery_status=DeliveryStatus.draft,
            delivery_comments=body.delivery_comments,
            task_grade_percentage=0,
        )
        session.add(delivery)
        session.commit()
        session.refresh(delivery)

        return BaseDataResponse(
            data=DeliverySchema.model_validate(delivery)
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft",
    methods=["GET"],
)
@openapi.summary("获取任务提交草稿")
@openapi.tag("任务提交接口")
@openapi.description("""获取任务提交草稿，返回任务提交的评论。""")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[DeliverySchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_draft(request, class_id: int, group_id: int, task_id: int):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    try:
        draft = service.delivery.get_task_draft(request, task_id, group_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=404, message=str(e))

    with db() as session:
        session.add(draft)
        return BaseDataResponse(
            data=DeliverySchema.model_validate(draft)
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft",
    methods=["PUT"],
)
@openapi.summary("更新任务提交草稿")
@openapi.tag("任务提交接口")
@openapi.description("""更新任务提交草稿，需要提供任务提交的评论。""")
@openapi.body(
    {
        "application/json": CreateDeliveryRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[DeliverySchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@validate(json=CreateDeliveryRequest)
async def update_draft(
    request, class_id: int, group_id: int, task_id: int, body: CreateDeliveryRequest
):
    db = request.app.ctx.db

    try:
        (
            group,
            class_member,
            is_manager,
            current_task,
        ) = service.delivery.check_can_create_draft(
            request, task_id=task_id, class_id=class_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    with db() as session:
        draft = service.delivery.get_task_draft(request, task_id, group_id)
        if not draft:
            return ErrorResponse.new_error(code=404, message="Draft not found.")

        draft.delivery_comments = body.delivery_comments
        draft.delivery_time = datetime.now()

        session.add(draft)
        session.commit()
        session.refresh(draft)

        return BaseDataResponse(
            data=DeliverySchema.model_validate(draft)
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft/item",
    methods=["POST"],
)
@openapi.summary("添加任务提交附件")
@openapi.tag("任务提交接口")
@openapi.description("""添加任务提交附件，需要提供附件的类型和 ID。""")
@openapi.body(
    {
        "application/json": AddDeliveryItemRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
)
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[DeliveryItemSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@validate(json=AddDeliveryItemRequest)
async def add_delivery_item(
    request, class_id: int, group_id: int, task_id: int, body: AddDeliveryItemRequest
):
    db = request.app.ctx.db

    try:
        (
            group,
            class_member,
            is_manager,
            current_task,
        ) = service.delivery.check_can_create_draft(
            request, task_id=task_id, class_id=class_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    with db() as session:
        delivery = service.delivery.get_task_draft(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Draft not found.")

        if DeliveryType(body.item_type) == DeliveryType.file:
            file, access = await service.file.check_has_access(request, body.item_id)
            if not access["read"] or not access["write"]:
                return ErrorResponse.new_error(
                    code=403,
                    message="You don't have the permission to access the file.",
                )
            copied_file = await service.file.copy_file_for_delivery(
                request, file.id, delivery.id
            )
            body.item_id = copied_file.id
        elif DeliveryType(body.item_type) == DeliveryType.repo:
            dup_stmt = select(DeliveryItem).where(
                and_(
                    DeliveryItem.item_type == body.item_type,
                    DeliveryItem.item_repo_id == body.item_id,
                )
            )
            dup_item = session.execute(dup_stmt).scalar()
            if dup_item:
                return ErrorResponse.new_error(
                    code=403, message="Item already exists in the draft."
                )

            stmt = select(RepoRecord).where(
                and_(
                    RepoRecord.group_id == group_id,
                    RepoRecord.id == body.item_id,
                    RepoRecord.status == RepoRecordStatus.completed,
                )
            )
            repo_record = session.execute(stmt).scalar()
            if not repo_record:
                return ErrorResponse.new_error(
                    code=404, message="Repo record not found or not completed."
                )
        else:
            return ErrorResponse.new_error(code=400, message="Invalid item type.")

        delivery_item = DeliveryItem(
            item_type=body.item_type,
            item_file_id=(
                body.item_id
                if DeliveryType(body.item_type) == DeliveryType.file
                else None
            ),
            item_repo_id=(
                body.item_id
                if DeliveryType(body.item_type) == DeliveryType.repo
                else None
            ),
            delivery_id=delivery.id,
        )
        session.add(delivery_item)
        session.add(delivery)
        delivery.delivery_items.append(delivery_item)

        session.merge(delivery)
        session.commit()
        session.refresh(delivery)

        return BaseDataResponse(
            data=DeliveryItemSchema.model_validate(delivery_item)
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft/item/<item_id:int>",
    methods=["DELETE"],
)
@openapi.summary("删除任务提交附件")
@openapi.tag("任务提交接口")
@openapi.description("""删除任务提交附件，需要提供附件的 ID。""")
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
async def delete_delivery_item(
    request, class_id: int, group_id: int, task_id: int, item_id: int
):
    db = request.app.ctx.db

    try:
        (
            group,
            class_member,
            is_manager,
            current_task,
        ) = service.delivery.check_can_create_draft(
            request, task_id=task_id, class_id=class_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    with db() as session:
        delivery = service.delivery.get_task_draft(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Draft not found.")

        delivery_item = session.query(DeliveryItem).get(item_id)
        if not delivery_item:
            return ErrorResponse.new_error(code=404, message="Item not found.")
        if delivery_item.delivery_id != delivery.id:
            return ErrorResponse.new_error(code=403, message="Item not in the draft.")

        session.delete(delivery_item)
        session.commit()

        return BaseResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/draft/submit",
    methods=["POST"],
)
@openapi.summary("提交任务提交草稿")
@openapi.tag("任务提交接口")
@openapi.description("""提交任务提交草稿，需要提供任务提交的评论。""")
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
async def submit_draft(request, class_id: int, group_id: int, task_id: int):
    db = request.app.ctx.db
    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    try:
        service.delivery.check_can_create_delivery(
            request, task_id=task_id, group_id=group_id
        )
    except ValueError as e:
        return ErrorResponse.new_error(code=403, message=str(e))

    with db() as session:
        draft: Delivery = service.delivery.get_task_draft(request, task_id, group_id)
        if not draft:
            return ErrorResponse.new_error(code=404, message="Draft not found.")

        if is_manager:
            draft.delivery_status = DeliveryStatus.teacher_review
        else:
            draft.delivery_status = DeliveryStatus.leader_review

        session.add(draft)
        session.commit()

        return BaseDataResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/review",
    methods=["GET"],
)
@openapi.summary("获取任务提交审核")
@openapi.tag("任务提交接口")
@openapi.description("""获取任务提交审核，返回任务提交的评论。""")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[DeliverySchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
async def get_review(request, class_id: int, group_id: int, task_id: int):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    with db() as session:
        delivery = service.delivery.get_task_latest_delivery(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Delivery not found.")
        session.add(delivery)

        return BaseDataResponse(
            data=DeliverySchema.model_validate(delivery)
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/review/approve",
    methods=["POST"],
)
@openapi.summary("审核任务提交通过")
@openapi.tag("任务提交接口")
@openapi.description("""审核任务提交通过，需要提供任务提交的分数。""")
@openapi.body(
    {
        "application/json": AcceptDeliveryRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(json=AcceptDeliveryRequest)
async def accept_review(
    request, class_id: int, group_id: int, task_id: int, body: AcceptDeliveryRequest
):
    db = request.app.ctx.db
    user = request.ctx.user

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    if not is_manager:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to review the delivery."
        )

    with db() as session:
        delivery = service.delivery.get_task_latest_delivery(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Delivery not found.")
        session.add(delivery)

        if delivery.delivery_status not in [
            DeliveryStatus.leader_review,
            DeliveryStatus.teacher_review,
            DeliveryStatus.teacher_rejected,
        ]:
            return ErrorResponse.new_error(
                code=403, message="Delivery status is not review."
            )

        if (
            delivery.delivery_status == DeliveryStatus.teacher_review
            and user.user_type == UserType.student
        ):
            return ErrorResponse.new_error(
                code=403, message="You don't have the permission to do it."
            )

        if user.user_type != UserType.student:
            delivery.delivery_status = DeliveryStatus.teacher_approved
            delivery.task_grade_percentage = body.score
            if not body.score:
                return ErrorResponse.new_error(code=400, message="Score is required.")
        else:
            delivery.delivery_status = DeliveryStatus.teacher_review

        session.add(delivery)
        session.commit()

        return BaseDataResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/review/reject",
    methods=["POST"],
)
@openapi.summary("审核任务提交拒绝")
@openapi.tag("任务提交接口")
@openapi.description("""审核任务提交拒绝，需要提供任务提交的评论。""")
@openapi.body(
    {
        "application/json": RejectDeliveryRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(json=RejectDeliveryRequest)
async def reject_review(
    request, class_id: int, group_id: int, task_id: int, body: RejectDeliveryRequest
):
    db = request.app.ctx.db
    user = request.ctx.user

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    if not is_manager:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to do it."
        )

    with db() as session:
        delivery = service.delivery.get_task_latest_delivery(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Delivery not found.")
        session.add(delivery)

        if delivery.delivery_status not in [
            DeliveryStatus.leader_review,
            DeliveryStatus.teacher_review,
            DeliveryStatus.teacher_approved,
        ]:
            return ErrorResponse.new_error(
                code=403, message="Delivery status is not able to reject."
            )

        if (
            delivery.delivery_status != DeliveryStatus.leader_review
            and user.user_type == UserType.student
        ):
            return ErrorResponse.new_error(
                code=403, message="You don't have the permission to do it."
            )

        if delivery.delivery_status == DeliveryStatus.leader_review:
            delivery.delivery_status = DeliveryStatus.leader_rejected
        else:
            delivery.delivery_status = DeliveryStatus.teacher_rejected
        delivery.delivery_comments = body.delivery_comments

        session.add(delivery)
        session.commit()

        return BaseDataResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/score",
    methods=["POST"],
)
@openapi.summary("评分任务提交")
@openapi.tag("任务提交接口")
@openapi.description("""评分任务提交，需要提供任务提交的分数和评分详情。""")
@openapi.body(
    {
        "application/json": ScoreDetailRequest.schema(
            ref_template="#/components/schemas/{model}"
        )
    }
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
@validate(json=ScoreDetailRequest)
async def score_review(
    request, class_id: int, group_id: int, task_id: int, body: ScoreDetailRequest
):
    db = request.app.ctx.db
    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    with db() as session:
        delivery = service.delivery.get_task_latest_delivery(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Delivery not found.")
        if delivery.delivery_status != DeliveryStatus.teacher_approved:
            return ErrorResponse.new_error(
                code=403, message="Delivery status is not approved."
            )

        user_id = body.user_id
        session.add(group)
        group_member_ids = [
            member.user_id for member in group.members if not member.is_teacher
        ]
        if user_id not in group_member_ids:
            return ErrorResponse.new_error(
                code=403, message="User is not in the group."
            )

        teacher_score = TeacherScore(
            task_id=task_id,
            user_id=body.user_id,
            score=body.score,
            score_time=datetime.now(),
            score_details=body.score_details,
        )
        session.merge(teacher_score)
        session.commit()

        return BaseDataResponse().json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/score",
    methods=["GET"],
)
@openapi.summary("获取任务提交评分")
@openapi.tag("任务提交接口")
@openapi.description("""获取任务提交评分，返回任务提交的分数和评分详情。""")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseListResponse[TeacherScoreSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def get_score_review(request, class_id: int, group_id: int, task_id: int):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    with db() as session:
        delivery = service.delivery.get_task_latest_delivery(request, task_id, group_id)
        if not delivery:
            return ErrorResponse.new_error(code=404, message="Delivery not found.")
        if delivery.delivery_status != DeliveryStatus.teacher_approved:
            return ErrorResponse.new_error(
                code=403, message="Delivery status is not approved."
            )

        score_list, _ = service.delivery.get_group_task_score(
            request, task_id, group_id
        )
        session.add_all(score_list)

        return BaseListResponse(
            data=[
                TeacherScoreSchema.model_validate(teacher_score)
                for teacher_score in score_list
            ]
        ).json_response()


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/next_task",
    methods=["POST"],
)
@openapi.summary("允许小组提交下一个任务")
@openapi.tag("任务提交接口")
@openapi.description("""允许小组提交下一个任务。""")
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
async def next_task(request, class_id: int, group_id: int):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id=class_id, group_id=group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to access the group."
        )

    with db() as session:
        latest_delivery = service.delivery.get_task_latest_delivery(
            request, group.current_task_id, group_id
        )
        if not latest_delivery:
            return ErrorResponse.new_error(
                code=404, message="No delivery for current task."
            )
        if latest_delivery.delivery_status != DeliveryStatus.teacher_approved:
            return ErrorResponse.new_error(
                code=403, message="Current task delivery is not approved."
            )
        _, is_complete = service.delivery.get_group_task_score(
            request, group.current_task_id, group_id
        )
        if not is_complete:
            return ErrorResponse.new_error(
                code=403, message="Current task score is not complete."
            )

        session.add(group)
        next_task_id = group.current_task.next_task_id
        if not next_task_id:
            return ErrorResponse.new_error(code=404, message="Already the last task.")
        group.current_task_id = next_task_id
        session.commit()

        return BaseResponse().json_response()
