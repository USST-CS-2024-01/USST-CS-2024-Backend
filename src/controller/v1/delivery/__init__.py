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
)
from middleware.auth import need_login
from middleware.validator import validate
from model import Delivery, DeliveryStatus, DeliveryType, DeliveryItem
from model.response_model import (
    ErrorResponse,
    BaseListResponse,
    BaseResponse,
    BaseDataResponse,
)
from model.schema import DeliverySchema, DeliveryItemSchema

delivery_bp = Blueprint("delivery")


@delivery_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/task/<task_id:int>/delivery/list",
    methods=["GET"],
)
@openapi.summary("获取任务提交列表")
@openapi.tag("任务提交接口")
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

    draft = service.delivery.get_task_draft(request, task_id, group_id)
    if draft:
        return ErrorResponse.new_error(
            code=403, message="You already have a draft for this task."
        )

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
            # TODO: Check repo access
            pass
        else:
            return ErrorResponse.new_error(code=400, message="Invalid item type.")

        delivery_item = DeliveryItem(
            item_type=body.item_type,
            item_file_id=body.item_id
            if DeliveryType(body.item_type) == DeliveryType.file
            else None,
            item_repo_id=body.item_id
            if DeliveryType(body.item_type) == DeliveryType.repo
            else None,
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
