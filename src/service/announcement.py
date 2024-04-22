from sqlalchemy import select

import service.class_
import service.group
from model import Announcement, AnnouncementReceiverType


def get_announcement(request, announcement_id: int) -> Announcement:
    """
    Get announcement by id
    :param request:  request
    :param announcement_id:  announcement id
    :return:
    """
    db = request.app.ctx.db
    user = request.ctx.user

    with db() as session:
        stmt = select(Announcement).where(Announcement.id.__eq__(announcement_id))
        announcement = session.execute(stmt).scalar()

        if not announcement:
            raise ValueError("Announcement not found")

        if announcement.receiver_type == AnnouncementReceiverType.all:
            pass
        elif announcement.publisher == user.id:
            pass
        elif announcement.receiver_type == AnnouncementReceiverType.class_:
            if not service.class_.has_class_access(
                request, class_id=announcement.receiver_class_id
            ):
                raise ValueError(
                    "You don't have the permission to view the announcement"
                )
        elif announcement.receiver_type == AnnouncementReceiverType.group:
            if not service.group.have_group_access_by_id(
                request, group_id=announcement.receiver_group_id
            ):
                raise ValueError(
                    "You don't have the permission to view the announcement"
                )
        elif announcement.receiver_type == AnnouncementReceiverType.individual:
            if announcement.receiver_user_id != user.id:
                raise ValueError(
                    "You don't have the permission to view the announcement"
                )
        elif announcement.receiver_type == AnnouncementReceiverType.role:
            if user.user_type != announcement.receiver_role:
                raise ValueError(
                    "You don't have the permission to view the announcement"
                )
        else:
            raise ValueError("Unknown receiver type")

        return announcement
