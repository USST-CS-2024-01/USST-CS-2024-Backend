from typing import List

from model import GroupMeetingAttachment


def update_group_meeting_attachment(request, meeting_id: int, attachments: List[int]):
    """
    Update group task attachment
    :param request: Request
    :param meeting_id: Group task ID
    :param attachments: Attachment list
    """
    with request.app.ctx.db() as session:
        # 先清除所有的 attachments
        stmt = GroupMeetingAttachment.__table__.delete().where(
            GroupMeetingAttachment.meeting_id == meeting_id
        )
        session.execute(stmt)

        if not attachments:
            session.commit()
            return

        # 再添加新的 attachments
        stmt = GroupMeetingAttachment.__table__.insert().values(
            [
                {"meeting_id": meeting_id, "file_id": attachment}
                for attachment in attachments
            ]
        )
        session.execute(stmt)

        session.commit()
