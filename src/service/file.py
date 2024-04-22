import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
from uuid import uuid4

from sqlalchemy import select

import service.class_
import service.group
from model import FileOwnerType, File, FileType, UserType, Delivery

SUPPORT_DOCUMENT = ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pdf"]


def generate_storage_path(
    owner_type: FileOwnerType, owner_id: int, file_name: str
) -> str:
    """
    Generate storage path
    :param owner_type: File owner type
    :param owner_id: File owner ID
    :param file_name: File name
    :return: Storage path
    """
    uuid = str(uuid4())
    return f"{owner_type.value}/{owner_id}/{int(time.time())}_{uuid}_{file_name}"


def generate_file_session_id() -> str:
    """
    Generate file session ID
    :return: File session ID
    """
    return f"file:{int(time.time())}_{uuid4()}"


def get_file_owner_id(file: File) -> int:
    """
    Get file owner ID
    :param file: File
    :return: File owner ID
    """
    if file.owner_type == FileOwnerType.delivery:
        return file.owner_delivery_id
    if file.owner_type == FileOwnerType.group:
        return file.owner_group_id
    if file.owner_type == FileOwnerType.user:
        return file.owner_user_id
    if file.owner_type == FileOwnerType.clazz:
        return file.owner_clazz_id
    return 0


async def start_upload_session(
    request, file_name: str, owner_type: FileOwnerType, owner_id: int
) -> (str, str):
    """
    Start upload session, return session
    :param request: Request
    :param file_name: File path
    :param owner_type: File owner type
    :param owner_id: File owner ID
    :return: File session ID and upload session
    """
    goflet = request.app.ctx.goflet
    cache = request.app.ctx.cache

    if len(file_name) > 500:
        raise ValueError("File name too long")

    file_path = generate_storage_path(owner_type, owner_id, file_name)
    ext = file_name.split(".")[-1]

    file = File(
        name=file_name,
        file_key=file_path,
        file_type=FileType.document if ext in SUPPORT_DOCUMENT else FileType.other,
        file_size=0,
        owner_type=owner_type,
        owner_delivery_id=owner_id if owner_type == FileOwnerType.delivery else None,
        owner_user_id=(
            owner_id if owner_type == FileOwnerType.user else request.ctx.user.id
        ),
        owner_group_id=owner_id if owner_type == FileOwnerType.group else None,
        owner_clazz_id=owner_id if owner_type == FileOwnerType.clazz else None,
        create_date=datetime.now(),
        modify_date=datetime.now(),
    )

    file_session_id = generate_file_session_id()
    await cache.set_pickle(file_session_id, file, expire=3600)

    return file_session_id, goflet.create_upload_session(file_path)


async def complete_upload_session(request, file_session_id: str) -> File:
    """
    Complete upload session
    :param request: Request
    :param file_session_id: File session ID
    :return: None
    """
    cache = request.app.ctx.cache
    db = request.app.ctx.db
    goflet = request.app.ctx.goflet

    file = await cache.get_pickle(file_session_id)
    if not file:
        raise ValueError("File session not found")

    file_key = file.file_key
    try:
        await goflet.complete_upload_session(file_key)

        file_meta = await goflet.get_file_meta(file_key)
        file.file_size = file_meta["fileSize"]
        file.modify_date = datetime.fromtimestamp(file_meta["lastModified"])
    except Exception as e:
        raise ValueError("File not found") from e

    with db() as session:
        session.add(file)
        session.commit()
        await cache.delete(file_session_id)
        session.refresh(file)
        return file


async def cancel_upload_session(request, file_session_id: str):
    """
    Cancel upload session
    :param request: Request
    :param file_session_id: File session ID
    :return: None
    """
    cache = request.app.ctx.cache
    goflet = request.app.ctx.goflet

    file = await cache.get_pickle(file_session_id)
    if not file:
        raise ValueError("File session not found")

    file_key = file.file_key
    try:
        await goflet.cancel_upload_session(file_key)
    except Exception as e:
        raise ValueError("File not found") from e

    await cache.delete(file_session_id)


async def check_has_access(request, file_id: int) -> (File, Dict[str, Any]):
    """
    Check whether the user has access to the file
    :param request: Request
    :param file_id: File ID
    :return: File
    """
    user = request.ctx.user
    db = request.app.ctx.db
    cache = request.app.ctx.cache

    tmp_access_key = f"file_access:{user.id}:{file_id}"

    access = {
        "read": True,
        "write": True,
        "delete": True,
        "annotate": True,
        "rename": True,
    }

    with db() as session:
        file = session.execute(select(File).where(File.id == file_id)).scalar()
        if not file:
            raise ValueError("File not found")

        # 若用户为管理员，则直接返回
        if user.user_type == UserType.admin:
            return file, access

        # 若文件为用户文件，且用户为文件所有者，则直接返回
        if file.owner_type == FileOwnerType.user and file.owner_user_id == user.id:
            return file, access

        # 若文件为小组文件，且用户为小组成员，则直接返回
        if file.owner_type == FileOwnerType.group:
            group_access, _, _ = service.group.have_group_access_by_id(
                request, file.owner_group_id
            )
            if group_access:
                return file, access

        # 若文件为班级文件，则需要判断用户角色是否为教师，若是，则可以对文件修改，否则只能查看
        if file.owner_type == FileOwnerType.clazz:
            clazz = service.class_.has_class_access(request, file.owner_clazz_id)
            if clazz:
                # 学生只能预览，不能进行任何操作
                if user.user_type == UserType.student:
                    access["write"] = False
                    access["delete"] = False
                    access["rename"] = False
                    access["annotate"] = False
                return file, access

        # 若文件为交付文件，需要进一步地判断
        if file.owner_type == FileOwnerType.delivery:
            delivery = session.execute(
                select(Delivery).where(Delivery.id == file.owner_delivery_id)
            ).scalar()
            if not delivery:
                raise ValueError("File not found")

            # 判断交付物所属小组是否为用户所在小组
            group_id = delivery.group_id
            group_access, _, _ = service.group.have_group_access_by_id(
                request, group_id
            )

            if group_access:
                access["write"] = False
                access["delete"] = False
                access["rename"] = False

                return file, access

        # 否则，检查用户是否有临时文件访问权限
        access = await cache.get_pickle(tmp_access_key)
        if not access:
            raise ValueError("File not found")

        return file, access


async def temp_file_access(request, file_id: int, access: Dict[str, Any], expire=3600):
    """
    Temp file access
    :param request: Request
    :param file_id: File ID
    :param access: Access
    :param expire: Expire time
    :return: None
    """
    user = request.ctx.user
    cache = request.app.ctx.cache

    tmp_access_key = f"file_access:{user.id}:{file_id}"
    await cache.set_pickle(tmp_access_key, access, expire=expire)


async def onlyoffice_callback(request, file_id: int, payload: Dict[str, Any]):
    """
    OnlyOffice callback
    :param request: Request
    :param file_id: File ID
    :param payload: Payload
    :return: None
    """
    db = request.app.ctx.db
    goflet = request.app.ctx.goflet
    cache = request.app.ctx.cache

    with db() as session:
        file = session.execute(select(File).where(File.id == file_id)).scalar()
        if not file:
            raise ValueError("File not found")

        if payload["status"] == 2:
            cache_key = f"onlyoffice:file:{file_id}"
            await cache.delete(cache_key)

            await goflet.onlyoffice_callback(payload, file.file_key)
            asyncio.create_task(async_update_file_meta(request, file))


async def async_update_file_meta(request, file):
    """
    Update file meta
    :param request: Request
    :param file: File
    :return: None
    """
    goflet = request.app.ctx.goflet
    db = request.app.ctx.db
    retries = 3
    with db() as session:
        session.add(file)
        while retries > 0:
            try:
                file_meta = await goflet.get_file_meta(file.file_key)
                file.file_size = file_meta["fileSize"]
                file.modify_date = datetime.fromtimestamp(file_meta["lastModified"])
                session.commit()
                break
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise e
                print(f"Retry update file meta: {file.id}, retries: {retries}")
                await asyncio.sleep(1)


async def delete_file(request, file_id: int):
    """
    Delete file
    :param request: Request
    :param file_id: File ID
    :return: None
    """
    db = request.app.ctx.db
    goflet = request.app.ctx.goflet
    cache = request.app.ctx.cache

    with db() as session:
        file = session.execute(select(File).where(File.id == file_id)).scalar()
        if not file:
            raise ValueError("File not found")

        await goflet.delete_file(file.file_key)
        session.delete(file)
        session.commit()

        cache_key = f"onlyoffice:file:{file_id}"
        await cache.delete(cache_key)


def check_file_in_group(request, group_id: int, file_ids: List[int]) -> List[File]:
    """
    Check whether the file is in the group
    :param request: Request
    :param group_id: Group ID
    :param file_ids: File IDs
    :return: File list
    """
    db = request.app.ctx.db

    with db() as session:
        files = (
            session.query(File)
            .filter(
                File.owner_group_id == group_id,
                File.id.in_(file_ids),
                File.owner_type == FileOwnerType.group,
            )
            .all()
        )
        if len(files) != len(file_ids):
            raise ValueError("Not all files are in the group")
        return files


async def grant_file_access(
    request, file_id: int, user_id: int, access: Dict[str, Any]
):
    """
    Grant file access
    :param request: Request
    :param file_id: File ID
    :param user_id: User ID
    :param access: Access
    :return: None
    """
    cache = request.app.ctx.cache

    tmp_access_key = f"file_access:{user_id}:{file_id}"
    d_access = {
        "read": False,
        "write": False,
        "delete": False,
        "annotate": False,
        "rename": False,
    }
    d_access.update(access)
    await cache.set_pickle(tmp_access_key, d_access, expire=3600)
