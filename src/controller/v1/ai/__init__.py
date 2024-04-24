from datetime import datetime

from kafka import KafkaProducer
from sanic import Blueprint
from sanic_ext.extensions.openapi import openapi
from sqlalchemy import func, select, or_

import service.announcement
import service.class_
import service.file
import service.group
from controller.v1.ai.request_model import CreateDocumentEvaluationRequest
from middleware.auth import need_login, need_role
from middleware.validator import validate
from model import (
    UserType,
    AIDocScoreRecord,
    AIDocStatus,
    FileOwnerType,
)
from model.response_model import (
    BaseResponse,
    ErrorResponse,
    BaseListResponse,
    BaseDataResponse,
)
from model.schema import AnnouncementSchema, AIDocScoreRecordSchema
import service.onlyoffice
import json as json_p

ai_bp = Blueprint("ai")


@ai_bp.route("/ai/document_evaluation/create", methods=["POST"])
@openapi.summary("创建文档评估")
@openapi.tag("AI接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
@validate(CreateDocumentEvaluationRequest)
async def create_document_evaluation(request, body: CreateDocumentEvaluationRequest):
    """
    创建文档评估
    """
    db = request.app.ctx.db
    producer: KafkaProducer = request.app.ctx.producer

    try:
        file, access = await service.file.check_has_access(request, body.file_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=400, message=str(e))

    if not access["read"]:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to read the file."
        )

    if file.owner_type != FileOwnerType.delivery:
        return ErrorResponse.new_error(
            code=400, message="The file is not a delivery file."
        )

    with db() as session:
        stmt = select(AIDocScoreRecord).where(
            AIDocScoreRecord.file_id.__eq__(body.file_id),
            AIDocScoreRecord.status.__ne__(AIDocStatus.failed),
        )
        record = session.execute(stmt).scalar()
        if record:
            return ErrorResponse.new_error(
                code=400, message="The document evaluation task already exists."
            )

        record = AIDocScoreRecord(
            file_id=body.file_id,
            status=AIDocStatus.pending,
            create_time=datetime.now(),
        )
        session.add(record)
        session.commit()

        session.refresh(record)
        producer.send(
            "scs-ai_doc_evaluation",
            json_p.dumps(
                {
                    "param": await service.onlyoffice.generate_file_conversion_params(
                        request, file, "txt"
                    ),
                    "onlyoffice_url": request.app.config["ONLYOFFICE_ENDPOINT"]
                    + "/ConvertService.ashx",
                    "task_id": record.id,
                    "status": str(record.status),
                }
            ).encode("utf-8"),
        )

    return BaseResponse().json_response()


@ai_bp.route("/file/<file_id:int>/document_evaluation", methods=["GET"])
@openapi.summary("获取文档评估")
@openapi.tag("AI接口")
@need_login()
async def get_document_evaluation(request, file_id: int):
    """
    获取文档评估
    """
    db = request.app.ctx.db

    try:
        file, access = await service.file.check_has_access(request, file_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=400, message=str(e))

    if not access["read"]:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to read the file."
        )

    with db() as session:
        stmt = (
            select(AIDocScoreRecord)
            .where(
                AIDocScoreRecord.file_id.__eq__(file_id),
            )
            .order_by(AIDocScoreRecord.create_time.desc())
            .limit(1)
        )
        record = session.execute(stmt).scalar()
        if not record:
            return ErrorResponse.new_error(
                code=404, message="The document evaluation task not found."
            )

        return BaseDataResponse(
            data=AIDocScoreRecordSchema.model_validate(record)
        ).json_response()


@ai_bp.route("/file/<file_id:int>/document_evaluation", methods=["PUT"])
@openapi.summary("重新发送文档评估请求")
@openapi.tag("AI接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def resend_document_evaluation(request, file_id: int):
    """
    重新发送文档评估请求
    """
    db = request.app.ctx.db
    producer: KafkaProducer = request.app.ctx.producer

    try:
        file, access = await service.file.check_has_access(request, file_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=400, message=str(e))

    if not access["read"]:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to read the file."
        )

    with db() as session:
        stmt = select(AIDocScoreRecord).where(
            AIDocScoreRecord.file_id.__eq__(file_id),
            AIDocScoreRecord.status.__ne__(AIDocStatus.completed),
        )
        record = session.execute(stmt).scalar()
        if not record:
            return ErrorResponse.new_error(
                code=404,
                message="Only pending or failed document evaluation task can be resent.",
            )

        producer.send(
            "scs-ai_doc_evaluation",
            json_p.dumps(
                {
                    "param": await service.onlyoffice.generate_file_conversion_params(
                        request, file, "txt"
                    ),
                    "onlyoffice_url": request.app.config["ONLYOFFICE_ENDPOINT"]
                    + "/ConvertService.ashx",
                    "task_id": record.id,
                    "status": str(record.status),
                }
            ).encode("utf-8"),
        )
        session.commit()

    return BaseResponse().json_response()


@ai_bp.route("/file/<file_id:int>/document_evaluation", methods=["DELETE"])
@openapi.summary("取消文档评估")
@openapi.tag("AI接口")
@need_login()
@need_role([UserType.admin, UserType.teacher])
async def cancel_document_evaluation(request, file_id: int):
    """
    取消文档评估
    """
    db = request.app.ctx.db

    try:
        file, access = await service.file.check_has_access(request, file_id)
    except ValueError as e:
        return ErrorResponse.new_error(code=400, message=str(e))

    if not access["read"]:
        return ErrorResponse.new_error(
            code=403, message="You don't have the permission to read the file."
        )

    with db() as session:
        stmt = select(AIDocScoreRecord).where(
            AIDocScoreRecord.file_id.__eq__(file_id),
            AIDocScoreRecord.status.__ne__(AIDocStatus.completed),
        )
        record = session.execute(stmt).scalar()
        if not record:
            return ErrorResponse.new_error(
                code=404,
                message="Only pending or failed document evaluation task can be canceled.",
            )

        session.delete(record)
        session.commit()

    return BaseResponse().json_response()
