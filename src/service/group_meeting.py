from datetime import datetime
from sqlalchemy import insert, update

from model import FileOwnerType, File, FileType, GroupMeeting
from service.file import generate_storage_path
import aiohttp


async def create_group_meeting_summary_file(
    request, meeting_name: str, meeting_id: int, group_id: int
):
    """
    Create a file for the meeting summary
    :param request: Request
    :param meeting_name: Meeting name
    :param meeting_id: Meeting ID
    :param group_id: Group ID
    """
    goflet = request.app.ctx.goflet
    db = request.app.ctx.db

    fname = f"{meeting_name}-会议纪要.docx"
    summary_file_path = generate_storage_path(FileOwnerType.group, group_id, fname)
    file_to_upload = open("template/meeting_summary.docx", "rb")
    file_size = file_to_upload.seek(0, 2)
    file_to_upload.seek(0)

    upload_url = goflet.create_upload_session(summary_file_path)
    async with aiohttp.ClientSession() as session:
        async with session.put(upload_url, data=file_to_upload) as response:
            response.raise_for_status()

    confirm_url = goflet.create_complete_upload_session(summary_file_path)
    async with aiohttp.ClientSession() as session:
        async with session.post(confirm_url) as response:
            response.raise_for_status()

    with db() as session:
        stmt = insert(File).values(
            name=fname,
            file_key=summary_file_path,
            file_type=FileType.document,
            file_size=file_size,
            owner_type=FileOwnerType.group,
            owner_group_id=group_id,
            create_date=datetime.now(),
            modify_date=datetime.now(),
        )
        result = session.execute(stmt)
        file_id = result.inserted_primary_key[0]
        session.commit()

        stmt = (
            update(GroupMeeting)
            .where(GroupMeeting.id.__eq__(meeting_id))
            .values(meeting_summary_file_id=file_id)
        )
        session.execute(stmt)
        session.commit()

    return file_id
