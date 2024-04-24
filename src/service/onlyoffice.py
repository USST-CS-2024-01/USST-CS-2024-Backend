import base64
import copy
import os
import time
import uuid
from datetime import datetime

import jwt
import aiohttp
import urllib3
from sqlalchemy import insert

import service.file
from model import File
from service.user import get_avatar_url

ONLY_OFFICE_BASIC_CONFIG = {
    "document": {
        "fileType": "",
        "key": "",
        "title": "",
        "url": "",
        "info": {
            "uploaded": "",
        },
        "permissions": {
            "chat": True,
            "comment": True,
            "copy": True,
            "download": True,
            "edit": True,
            "fillForms": True,
            "modifyContentControl": True,
            "print": True,
            "protect": False,
            "review": True,
            "deleteCommentAuthorOnly": True,
            "editCommentAuthorOnly": True,
        },
    },
    "documentType": "",
    "editorConfig": {
        "callbackUrl": "",
        "coEditing": {"mode": "fast", "change": True},
        "user": {"id": "", "image": "https://gravatar.com/avatar/", "name": ""},
        "mode": "edit",
    },
}

DOCUMENT_MAP = {
    "doc": "word",
    "docx": "word",
    "xls": "cell",
    "xlsx": "cell",
    "ppt": "slide",
    "pptx": "slide",
    "pdf": "pdf",
}

DOCBUILDER_CONVERT_TO_NO_COMMENT = open("template/convert_to_no_comment.js", "r").read()


def generate_tmp_file_key(file_id: int) -> str:
    """
    生成临时文件key
    :param file_id: 文件ID
    :return: 临时文件key
    """
    random_suffix = base64.b32encode(os.urandom(16)).decode("utf-8").replace("=", "")
    timestamp = int(time.time())
    return f"{file_id}-{timestamp}-{random_suffix}"


async def get_file_tmp_key(request, file_id: int) -> str:
    """
    获取文件临时key
    :param request: Request
    :param file_id: 文件ID
    :return: 文件临时key
    """
    cache = request.app.ctx.cache

    cache_key = f"onlyoffice:file:{file_id}"
    tmp_key = await cache.get(cache_key)
    if tmp_key is None:
        tmp_key = generate_tmp_file_key(file_id)
        await cache.set(cache_key, tmp_key, expire=7 * 24 * 60 * 60)
        return tmp_key
    return tmp_key.decode()


async def check_onlyoffice_access(request, file_id: int):
    """
    检查请求是否来自OnlyOffice
    :param request: Request
    :param file_id: 文件ID
    :return: None
    """
    authorization = request.headers.get("Authorization")
    if authorization is None and request.json is not None and "token" in request.json:
        authorization = f"Bearer {request.json['token']}"
    if authorization is None and request.args.get("token") is not None:
        authorization = f"Bearer {request.args['token'][0]}"
    if authorization is None:
        raise Exception("Unauthorized")
    if not authorization.startswith("Bearer "):
        raise Exception("Unauthorized")

    token = authorization[7:]
    try:
        jwt_decoded = jwt.decode(
            token, request.app.config["ONLYOFFICE_SECRET"], algorithms=["HS256"]
        )
        payload = jwt_decoded.get("payload")

        if not payload:
            raise Exception("Unauthorized")

        if payload.get("key"):
            file_key = payload["key"]
            tmp_key = await get_file_tmp_key(request, file_id)
            if file_key != tmp_key:
                raise Exception("Unauthorized")
        elif payload.get("url"):
            url = payload["url"]
            # 解析url的path部分
            path = urllib3.util.parse_url(url).path
            # /file/<file_id:int>/onlyoffice/download
            ends_with = [
                f"/file/{file_id}/onlyoffice/download",
                f"/file/{file_id}/onlyoffice/task/convert_to_no_comment",
            ]
            if not url.startswith(request.app.config["API_BASE_URL"]):
                raise Exception("Unauthorized")
            if not any(path.endswith(end) for end in ends_with):
                raise Exception("Unauthorized")
        else:
            raise Exception("Unauthorized")
    except Exception:
        raise Exception("Unauthorized")


async def generate_onlyoffice_config(request, file, access):
    """
    生成OnlyOffice配置
    :param request: Request
    :param file: 文件
    :param access: 文件访问权限
    :return: OnlyOffice配置
    """

    ext = file.name.split(".")[-1]
    if ext not in DOCUMENT_MAP:
        raise ValueError("Unsupported file type")

    if not access["read"]:
        raise ValueError("No access to the file")

    api_base = request.app.config["API_BASE_URL"]

    onlyoffice_config = copy.deepcopy(ONLY_OFFICE_BASIC_CONFIG)
    onlyoffice_config["documentType"] = DOCUMENT_MAP[ext]
    onlyoffice_config["document"]["fileType"] = ext
    onlyoffice_config["document"]["key"] = await get_file_tmp_key(request, file.id)
    onlyoffice_config["document"]["title"] = file.name
    onlyoffice_config["document"][
        "url"
    ] = f"{api_base}/api/v1/file/{file.id}/onlyoffice/download"
    onlyoffice_config["document"]["info"]["uploaded"] = file.create_date.isoformat()
    onlyoffice_config["editorConfig"][
        "callbackUrl"
    ] = f"{api_base}/api/v1/file/{file.id}/onlyoffice/callback"
    onlyoffice_config["editorConfig"]["user"]["id"] = request.ctx.user.id
    onlyoffice_config["editorConfig"]["user"]["name"] = request.ctx.user.name
    onlyoffice_config["editorConfig"]["user"]["image"] = await get_avatar_url(
        request, request.ctx.user.id
    )

    if not access["write"]:
        onlyoffice_config["document"]["permissions"]["edit"] = False
        onlyoffice_config["document"]["permissions"]["fillForms"] = False
        onlyoffice_config["document"]["permissions"]["modifyContentControl"] = False
        onlyoffice_config["document"]["permissions"]["review"] = False

    if not access["annotate"]:
        onlyoffice_config["document"]["permissions"]["comment"] = False

    onlyoffice_config["token"] = jwt.encode(
        onlyoffice_config,
        request.app.config["ONLYOFFICE_SECRET"],
    )

    return onlyoffice_config


async def get_template_convert_to_no_comment(request, file: File):
    """
    渲染转换为无批注文档模板，返回渲染后的内容
    :param file: 文件
    :param request: Request
    :return: None
    """
    f = DOCBUILDER_CONVERT_TO_NO_COMMENT
    api_base = request.app.config["API_BASE_URL"]

    download_url = f"{api_base}/api/v1/file/{file.id}/onlyoffice/download"
    token = jwt.encode(
        {
            "payload": {"url": download_url},
            "iat": int(time.time()),
            "exp": int(time.time()) + 5 * 60,
        },
        request.app.config["ONLYOFFICE_SECRET"],
    )

    f = f.replace("${fileUrl}", f"{download_url}?token={token}").replace(
        "${ext}", file.name.split(".")[-1]
    )

    return f


async def convert_to_no_comment(request, file: File, new_file_name: str) -> File:
    """
    转换为无批注文档
    :param request: Request
    :param file: 文件
    :param new_file_name: 新文件名
    :return: None
    """
    goflet = request.app.ctx.goflet
    db = request.app.ctx.db

    payload = {
        "async": False,
        "url": f"{request.app.config['API_BASE_URL']}/api/v1/file/{file.id}/onlyoffice/task/convert_to_no_comment",
    }
    token = jwt.encode(
        payload,
        request.app.config["ONLYOFFICE_SECRET"],
    )
    data = {
        "token": token,
    }

    aio_request = aiohttp.request(
        "POST", f"{request.app.config['ONLYOFFICE_ENDPOINT']}/docbuilder", json=data
    )
    async with aio_request as response:
        response.raise_for_status()
        output_fname = f"output.{file.name.split('.')[-1]}"

        output_url = await response.json()
        output_url = output_url["urls"][output_fname]
        file_path = service.file.generate_storage_path(
            file.owner_type, service.file.get_file_owner_id(file), new_file_name
        )

    new_file = copy.deepcopy(file)
    new_file.id = None
    new_file.name = new_file_name
    new_file.path = file_path
    new_file.create_date = datetime.now()
    await goflet.create_empty_file(file_path)
    await goflet.onlyoffice_callback(
        {
            "status": 2,
            "url": output_url,
        },
        file_path,
    )
    file_meta = await goflet.get_file_meta(file_path)
    new_file.file_size = file_meta["fileSize"]
    new_file.modify_date = datetime.fromtimestamp(file_meta["lastModified"])

    with db() as session:
        stmt = insert(File).values(
            name=new_file.name,
            file_key=new_file.path,
            file_type=new_file.file_type,
            file_size=new_file.file_size,
            owner_type=new_file.owner_type,
            owner_delivery_id=new_file.owner_delivery_id,
            owner_user_id=new_file.owner_user_id,
            owner_group_id=new_file.owner_group_id,
            owner_clazz_id=new_file.owner_clazz_id,
            create_date=new_file.create_date,
            modify_date=new_file.modify_date,
        )
        result = session.execute(stmt)
        new_file.id = result.inserted_primary_key[0]

        session.commit()

    return new_file


async def generate_file_conversion_params(
    request, file: File, target_file_type: str
) -> dict:
    """
    生成文件转换参数
    :param request:             Request
    :param file:                File
    :param target_file_type:    目标文件类型
    :return:                    文件转换参数
    """
    goflet = request.app.ctx.goflet

    params = {
        "async": False,
        "filetype": file.name.split(".")[-1],
        "outputtype": target_file_type,
        "url": goflet.create_download_url(file.file_key),
        "key": f"{int(time.time())}_{uuid.uuid4()}",
    }
    token = jwt.encode(
        params,
        request.app.config["ONLYOFFICE_SECRET"],
    )

    return {
        "token": token,
    }
