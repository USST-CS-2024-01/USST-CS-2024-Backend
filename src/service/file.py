import time
from datetime import datetime
from uuid import uuid4

from model import FileOwnerType, File, FileType

SUPPORT_DOCUMENT = ["doc", "docx", "xls", "xlsx", "ppt", "pptx"]


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
        owner_user_id=owner_id if owner_type == FileOwnerType.user else None,
        owner_group_id=owner_id if owner_type == FileOwnerType.group else None,
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
        goflet.complete_upload_session(file_key)

        file_meta = goflet.get_file_meta(file_key)
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
        goflet.cancel_upload_session(file_key)
    except Exception as e:
        raise ValueError("File not found") from e

    await cache.delete(file_session_id)
