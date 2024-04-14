import base64
import os
import time

import jwt
import urllib3

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
    if authorization is None:
        authorization = request.json.get("token")
        if authorization is None:
            raise Exception("Unauthorized")
        authorization = f"Bearer {authorization}"
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
            ends_with = f"/file/{file_id}/onlyoffice/download"
            if not path.endswith(ends_with):
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

    onlyoffice_config = ONLY_OFFICE_BASIC_CONFIG.copy()
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
