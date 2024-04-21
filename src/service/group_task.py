from typing import List

from model import GroupTaskAssignee, GroupTaskAttachment


def update_group_task_assignee(request, group_task_id: int, assignees: List[int]):
    """
    Update group task assignee
    :param request: Request
    :param group_task_id: Group task ID
    :param assignees: Assignee list
    """
    with request.app.ctx.db() as session:
        # 先清除所有的 assignees
        stmt = GroupTaskAssignee.__table__.delete().where(
            GroupTaskAssignee.task_id == group_task_id
        )
        session.execute(stmt)
        # 再添加新的 assignees
        stmt = GroupTaskAssignee.__table__.insert().values(
            [{"task_id": group_task_id, "role_id": assignee} for assignee in assignees]
        )
        session.execute(stmt)

        session.commit()


def update_group_task_attachment(request, group_task_id: int, attachments: List[int]):
    """
    Update group task attachment
    :param request: Request
    :param group_task_id: Group task ID
    :param attachments: Attachment list
    """
    with request.app.ctx.db() as session:
        # 先清除所有的 attachments
        stmt = GroupTaskAttachment.__table__.delete().where(
            GroupTaskAttachment.task_id == group_task_id
        )
        session.execute(stmt)

        if not attachments:
            session.commit()
            return

        # 再添加新的 attachments
        stmt = GroupTaskAttachment.__table__.insert().values(
            [
                {"task_id": group_task_id, "file_id": attachment}
                for attachment in attachments
            ]
        )
        session.execute(stmt)

        session.commit()
