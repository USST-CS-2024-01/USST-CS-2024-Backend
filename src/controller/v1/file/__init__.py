import json
import traceback

from sanic import Blueprint, html, redirect, raw
from sanic import json as sanic_json
from sanic_ext.extensions.openapi import openapi

import service.class_
import service.file
import service.group
import service.onlyoffice
from controller.v1.file.request_model import CreateFileRequest, UpdateFileRequest
from controller.v1.file.response_model import UploadSessionResponse
from middleware.auth import need_login
from middleware.validator import validate
from model import FileOwnerType, UserType, Group
from model.response_model import ErrorResponse, BaseDataResponse
from model.schema import FileSchema

file_bp = Blueprint("file")
ONLYOFFICE_TEMPLATE = open("template/onlyoffice.html", "r").read()


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
        # Delivery 类型不能直接上传文件
        return ErrorResponse.new_error(400, "Invalid owner type")

    elif body.owner_type == FileOwnerType.clazz:
        clazz = service.class_.has_class_access(request, body.owner_id)
        if not clazz or user.user_type != UserType.teacher:
            return ErrorResponse.new_error(403, "Permission denied")

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


@file_bp.route("/file/<file_id:int>", methods=["GET"])
@openapi.summary("获取文件信息")
@openapi.tag("文件接口")
@need_login()
async def get_file_info(request, file_id: int):
    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(404, str(e))

    if not access["read"]:
        return ErrorResponse.new_error(403, "No access to the file")

    return BaseDataResponse(data=FileSchema.model_validate(file)).json_response()


@file_bp.route("/file/<file_id:int>", methods=["DELETE"])
@openapi.summary("删除文件")
@openapi.tag("文件接口")
@need_login()
async def delete_file(request, file_id: int):
    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(400, str(e))

    if not access["delete"]:
        return ErrorResponse.new_error(403, "No access to the file")

    try:
        await service.file.delete_file(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(400, str(e))

    return BaseDataResponse().json_response()


@file_bp.route("/file/<file_id:int>", methods=["PUT"])
@openapi.summary("修改文件信息")
@openapi.tag("文件接口")
@need_login()
@validate(json=UpdateFileRequest)
async def update_file_info(request, file_id: int, body: UpdateFileRequest):
    db = request.app.ctx.db
    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(404, str(e))

    new_file_name = body.file_name
    if new_file_name:
        if not access["rename"]:
            return ErrorResponse.new_error(403, "No access to rename the file")

    with db() as session:
        session.add(file)
        file.name = new_file_name
        session.commit()

    return BaseDataResponse().json_response()


@file_bp.route("/file/<file_id:int>/download", methods=["GET"])
@openapi.summary("下载文件")
@openapi.tag("文件接口")
@need_login()
async def download_file(request, file_id: int):
    goflet = request.app.ctx.goflet

    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(404, str(e))

    if not access["read"]:
        return ErrorResponse.new_error(403, "No access to the file")

    return BaseDataResponse(
        data=goflet.create_download_url(file.file_key)
    ).json_response()


@file_bp.route("/file/<file_id:int>/onlyoffice/download", methods=["GET"])
@openapi.summary("OnlyOffice客户端获取文件")
@openapi.tag("文件接口")
@openapi.description(
    """
    该接口仅用于OnlyOffice客户端获取文件，用户不应直接访问该接口
"""
)
async def onlyoffice_download_file(request, file_id: int):
    goflet = request.app.ctx.goflet
    db = request.app.ctx.db

    try:
        await service.onlyoffice.check_onlyoffice_access(request, file_id)
    except Exception:
        traceback.print_exc()
        return ErrorResponse.new_error(401, "Unauthorized")

    with db() as session:
        file = (
            session.query(service.file.File)
            .filter(service.file.File.id == file_id)
            .one_or_none()
        )
        if not file:
            return ErrorResponse.new_error(404, "File not found")

    return redirect(goflet.create_download_url(file.file_key))


@file_bp.route("/file/<file_id:int>/onlyoffice/view", methods=["GET"])
@openapi.summary("渲染OnlyOffice文件")
@openapi.tag("文件接口")
@need_login(where="query")
async def onlyoffice_view_file(request, file_id: int):
    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception as e:
        return ErrorResponse.new_error(404, str(e))

    try:
        onlyoffice_config = await service.onlyoffice.generate_onlyoffice_config(
            request, file, access
        )
    except Exception as e:
        traceback.print_exc()
        return ErrorResponse.new_error(400, str(e))

    json_config = json.dumps(onlyoffice_config)
    onlyoffice_endpoint = request.app.config["ONLYOFFICE_ENDPOINT"]
    file_name = file.name

    html_data = (
        ONLYOFFICE_TEMPLATE.replace("${endpoint}", onlyoffice_endpoint)
        .replace("${config}", json_config)
        .replace("${filename}", file_name)
    )

    return html(html_data)


@file_bp.route("/file/<file_id:int>/onlyoffice/callback", methods=["POST"])
@openapi.summary("OnlyOffice回调")
@openapi.tag("文件接口")
async def onlyoffice_callback(request, file_id: int):
    try:
        await service.onlyoffice.check_onlyoffice_access(request, file_id)
    except Exception as e:
        traceback.print_exc()
        return ErrorResponse.new_error(401, str(e))
    try:
        await service.file.onlyoffice_callback(request, file_id, request.json)
    except Exception as e:
        traceback.print_exc()
        return ErrorResponse.new_error(400, str(e))

    return sanic_json({"error": 0})


@file_bp.route(
    "/file/<file_id:int>/onlyoffice/task/convert_to_no_comment",
    methods=["GET"],
)
@openapi.summary("Onlyoffice获取转换为无批注文档任务")
@openapi.tag("文件接口")
async def convert_to_no_comment(request, file_id: int):
    try:
        await service.onlyoffice.check_onlyoffice_access(request, file_id)
    except Exception:
        return ErrorResponse.new_error(401, "Unauthorized")

    db = request.app.ctx.db
    with db() as session:
        file = (
            session.query(service.file.File)
            .filter(service.file.File.id == file_id)
            .one_or_none()
        )

        if file.file_size > 100 * 1024 * 1024:
            return ErrorResponse.new_error(400, "File too large")

        if not file:
            return ErrorResponse.new_error(404, "File not found")

    try:
        return raw(
            await service.onlyoffice.get_template_convert_to_no_comment(request, file),
            content_type="application/javascript",
        )
    except Exception as e:
        return ErrorResponse.new_error(400, str(e))


@file_bp.route(
    "/file/<file_id:int>/onlyoffice/task/convert_to_no_comment", methods=["POST"]
)
@openapi.summary("转换为无批注文档")
@openapi.tag("文件接口")
@need_login()
@validate(json=UpdateFileRequest)
async def convert_to_no_comment_post(request, file_id: int, body: UpdateFileRequest):
    try:
        file, access = await service.file.check_has_access(request, file_id)
    except Exception:
        return ErrorResponse.new_error(401, "Unauthorized")
    if not access["write"]:
        return ErrorResponse.new_error(403, "Permission denied")
    if file.file_size > 100 * 1024 * 1024:
        return ErrorResponse.new_error(400, "File too large")

    new_file_name = body.file_name or "NoComment_" + file.name
    ext = file.name.split(".")[-1]
    if not new_file_name.endswith(ext):
        new_file_name += "." + ext

    try:
        new_file = await service.onlyoffice.convert_to_no_comment(
            request, file, new_file_name
        )
        return BaseDataResponse(
            data=FileSchema.model_validate(new_file)
        ).json_response()

    except Exception as e:
        return ErrorResponse.new_error(400, str(e))
