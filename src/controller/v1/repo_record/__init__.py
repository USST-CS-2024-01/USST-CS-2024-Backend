import json as p_json
import time
import uuid
from datetime import datetime

from kafka import KafkaProducer
from sanic import Blueprint
from sanic_ext import openapi
from sqlalchemy import select, and_

import service.class_
import service.group
from controller.v1.repo_record.request_model import ListRepoRequest, CreateRepoRequest
from middleware.auth import need_login
from middleware.validator import validate
from model import RepoRecord, RepoRecordStatus, Config
from model.response_model import (
    ErrorResponse,
    BaseListResponse,
    BaseDataResponse,
)
from model.schema import RepoRecordSchema

repo_record_bp = Blueprint("repo_record")


def generate_archive_file_key(task_id: int):
    return f"repo/{task_id}/archive_{int(time.time())}_{uuid.uuid4()}.zip"


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/list", methods=["GET"]
)
@openapi.summary("获取小组的仓库记录")
@openapi.tag("仓库记录")
@need_login()
@validate(query=ListRepoRequest)
async def list_group_repo_record(
    request, class_id: int, group_id: int, query: ListRepoRequest
):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    stmt = select(RepoRecord).where(
        RepoRecord.group_id.__eq__(group_id),
    )
    if query.status:
        stmt = stmt.where(RepoRecord.status.__eq__(query.status))
    if query.order_by:
        stmt = stmt.order_by(
            # 此处使用 getattr 函数获取排序字段，asc和desc是function类型，需要调用
            getattr(
                getattr(RepoRecord, query.order_by), query.asc and "asc" or "desc"
            )()
        )
    stmt = stmt.limit(100)

    with db() as session:
        repo_records = session.execute(stmt).scalars().all()
        data = [
            RepoRecordSchema.model_validate(repo_record) for repo_record in repo_records
        ]
        return BaseListResponse(
            data=data,
            total=len(data),
        ).json_response()


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/<repo_record_id:int>",
    methods=["GET"],
)
@openapi.summary("获取小组的仓库记录详情")
@openapi.tag("仓库记录")
@need_login()
async def get_group_repo_record(
    request, class_id: int, group_id: int, repo_record_id: int
):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        repo_record = session.execute(
            select(RepoRecord).where(
                and_(
                    RepoRecord.group_id.__eq__(group_id),
                    RepoRecord.id.__eq__(repo_record_id),
                )
            )
        )
        repo_record = repo_record.scalar()
        if not repo_record:
            return ErrorResponse.new_error(
                code=404,
                message="Repo record not found",
            )
        return BaseDataResponse(
            data=RepoRecordSchema.model_validate(repo_record),
        ).json_response()


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/<repo_record_id:int>/archive",
    methods=["GET"],
)
@openapi.summary("下载仓库记录归档")
@openapi.tag("仓库记录")
@need_login()
async def archive_group_repo_record(
    request, class_id: int, group_id: int, repo_record_id: int
):
    db = request.app.ctx.db
    goflet = request.app.ctx.goflet

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        repo_record = session.execute(
            select(RepoRecord).where(
                and_(
                    RepoRecord.group_id.__eq__(group_id),
                    RepoRecord.id.__eq__(repo_record_id),
                    RepoRecord.status.__eq__(RepoRecordStatus.completed),
                    RepoRecord.archive_file_id.isnot(None),
                )
            )
        )
        repo_record = repo_record.scalar()
        if not repo_record:
            return ErrorResponse.new_error(
                code=404,
                message="Repo record not found or not completed",
            )
        file = repo_record.archive
        if not file:
            return ErrorResponse.new_error(
                code=404,
                message="Archive not found",
            )
        return BaseDataResponse(
            data=goflet.create_download_url(file.file_key)
        ).json_response()


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/create",
    methods=["POST"],
)
@openapi.summary("创建仓库记录")
@openapi.tag("仓库记录")
@need_login()
@validate(json=CreateRepoRequest)
async def create_group_repo_record(
    request, class_id: int, group_id: int, body: CreateRepoRequest
):
    db = request.app.ctx.db
    producer: KafkaProducer = request.app.ctx.producer
    goflet = request.app.ctx.goflet

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    repo_record = RepoRecord(
        group_id=group_id,
        repo_url=body.repo_url,
        status=RepoRecordStatus.pending,
        create_time=datetime.now(),
    )
    username_map = {}

    with db() as session:
        session.add(group)
        for member in group.members:
            for u in member.repo_usernames:
                username_map[u] = member.user_id
        repo_record.username_map = username_map
        session.add(repo_record)
        session.commit()
        session.refresh(repo_record)

        file_key = generate_archive_file_key(repo_record.id)
        exp = goflet.jwt_expiration
        goflet.jwt_expiration = 3600 * 24 * 7
        sent = producer.send(
            "scs-git_stats",
            p_json.dumps(
                {
                    "id": repo_record.id,
                    "file_key": file_key,
                    "upload_url": goflet.create_upload_session(file_key),
                    "complete_url": goflet.create_complete_upload_session(file_key),
                    "repo_url": repo_record.repo_url,
                }
            ).encode(),
        )
        print(sent)
        goflet.jwt_expiration = exp

        return BaseDataResponse(
            data=RepoRecordSchema.model_validate(repo_record),
        ).json_response()


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/<repo_record_id:int>",
    methods=["DELETE"],
)
@openapi.summary("删除仓库记录")
@openapi.tag("仓库记录")
@need_login()
async def delete_group_repo_record(
    request, class_id: int, group_id: int, repo_record_id: int
):
    db = request.app.ctx.db

    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    with db() as session:
        repo_record = session.execute(
            select(RepoRecord).where(
                and_(
                    RepoRecord.group_id.__eq__(group_id),
                    RepoRecord.id.__eq__(repo_record_id),
                )
            )
        )
        repo_record = repo_record.scalar()
        if not repo_record:
            return ErrorResponse.new_error(
                code=404,
                message="Repo record not found",
            )
        if repo_record.status not in [
            RepoRecordStatus.pending,
            RepoRecordStatus.failed,
        ]:
            return ErrorResponse.new_error(
                code=403,
                message="Cannot delete a repo record that is not pending or failed",
            )
        session.delete(repo_record)
        session.commit()
        return BaseDataResponse().json_response()


@repo_record_bp.route(
    "/class/<class_id:int>/group/<group_id:int>/repo_record/public_key",
    methods=["GET"],
)
@openapi.summary("获取公钥")
@openapi.tag("仓库记录")
@need_login()
async def get_public_key(request, class_id: int, group_id: int):
    group, class_member, is_manager = service.group.have_group_access(
        request, class_id, group_id
    )
    if not group:
        return ErrorResponse.new_error(
            code=404,
            message="Group not found",
        )

    db = request.app.ctx.db
    with db() as session:
        repo_record = (
            session.query(Config).filter(Config.key == "git:ssh_public_key").first()
        )
        if not repo_record:
            return ErrorResponse.new_error(
                code=404,
                message="Public key not found",
            )
        key = repo_record.value
        return BaseDataResponse(data=key).json_response()
