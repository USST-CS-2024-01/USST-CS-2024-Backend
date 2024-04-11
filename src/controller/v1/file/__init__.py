from sanic import Blueprint
from sanic_ext.extensions.openapi import openapi

import service.file
import service.group
from controller.v1.file.request_model import CreateFileRequest
from controller.v1.file.response_model import UploadSessionResponse
from middleware.auth import need_login
from middleware.validator import validate
from model import FileOwnerType, UserType, Group
from model.response_model import ErrorResponse, BaseDataResponse
from model.schema import FileSchema

file_bp = Blueprint("file")


@file_bp.route("/file/upload", methods=["POST"])
@openapi.summary("开始文件上传会话")
@openapi.tag("文件接口")
@openapi.description("开始文件上传会话，返回上传会话ID和上传URL")
@need_login()
@validate(json=CreateFileRequest)
async def start_file_upload_session(request, body: CreateFileRequest):
    user = request.ctx.user
    db = request.app.ctx.db

    if body.owner_type == FileOwnerType.user:
        if body.owner_id is None:
            body.owner_id = user.id

        if body.owner_id != user.id and user.user_type != UserType.admin:
            return ErrorResponse.new_error(
                403,
                "You can only upload files for yourself",
            )
    elif body.owner_type == FileOwnerType.group:
        if body.owner_id is None:
            return ErrorResponse.new_error(400, "Group ID required")

        with db() as session:
            class_id = (
                session.query(Group.class_id).filter(Group.id == body.owner_id).scalar()
            )
            if not class_id:
                return ErrorResponse.new_error(404, "Group not found")

            group, self_class_member, is_manager = service.group.have_group_access(
                request, class_id, body.owner_id
            )
            if not group:
                return ErrorResponse.new_error(404, "Group not found")
    elif body.owner_type == FileOwnerType.delivery:
        if body.owner_id is None:
            return ErrorResponse.new_error(400, "Delivery ID required")

        # TODO: Check delivery access

    session_id, upload_url = await service.file.start_upload_session(
        request, body.file_name, body.owner_type, body.owner_id
    )

    response = UploadSessionResponse(session_id=session_id, upload_url=upload_url)
    return response.json_response()


@file_bp.route("/file/upload/<session_id:str>", methods=["POST"])
@openapi.summary("完成文件上传会话")
@openapi.tag("文件接口")
@openapi.description("完成文件上传会话，返回文件信息")
@need_login()
async def complete_file_upload_session(request, session_id: str):
    try:
        file = await service.file.complete_upload_session(request, session_id)
    except Exception as e:
        return ErrorResponse.new_error(400, str(e))

    return BaseDataResponse(data=FileSchema.model_validate(file)).json_response()


@file_bp.route("/file/upload/<session_id:str>", methods=["DELETE"])
@openapi.summary("取消文件上传会话")
@openapi.tag("文件接口")
@openapi.description("取消文件上传会话")
@need_login()
async def cancel_file_upload_session(request, session_id: str):
    try:
        await service.file.cancel_upload_session(request, session_id)
    except Exception as e:
        return ErrorResponse.new_error(400, str(e))
    return BaseDataResponse().json_response()
