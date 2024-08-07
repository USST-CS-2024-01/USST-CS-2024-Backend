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
@openapi.description(
    """创建文档评估任务，需要提供文件ID，仅类型为delivery的文件可以进行评估。
    评估任务创建成功后，会将任务信息发送到AI评估队列中，等待AI评估服务处理。"""
)
@openapi.body(
    {
        "application/json": CreateDocumentEvaluationRequest.schema(
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

        request.app.ctx.log.add_log(
            request=request,
            log_type="ai:create_document_evaluation",
            content=f"Create document evaluation task {record.id}",
        )
    return BaseResponse().json_response()


@ai_bp.route("/file/<file_id:int>/document_evaluation", methods=["GET"])
@openapi.summary("获取文档评估")
@openapi.tag("AI接口")
@openapi.description("""获取文档评估任务信息，返回最新的一条评估记录。""")
@openapi.response(
    200,
    description="成功",
    content={
        "application/json": BaseDataResponse[AIDocScoreRecordSchema].schema(
            ref_template="#/components/schemas/{model}"
        )
    },
)
@openapi.secured("session")
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
@openapi.description("""重新发送文档评估请求，仅对状态为pending或failed的任务有效。""")
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

        request.app.ctx.log.add_log(
            request=request,
            log_type="ai:resend_document_evaluation",
            content=f"Resend document evaluation task {record.id}",
        )

    return BaseResponse().json_response()


@ai_bp.route("/file/<file_id:int>/document_evaluation", methods=["DELETE"])
@openapi.summary("取消文档评估")
@openapi.tag("AI接口")
@openapi.description("""取消文档评估任务，仅对状态为pending或failed的任务有效。""")
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

        request.app.ctx.log.add_log(
            request=request,
            log_type="ai:cancel_document_evaluation",
            content=f"Cancel document evaluation task {record.id}",
        )
    return BaseResponse().json_response()
