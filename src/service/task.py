# _*_ coding: utf-8 _*_
"""
Time:     2024/4/16 15:13
Author:   不做评论(vvbbnn00)
Version:  
File:     task.py
Describe: 
"""
from typing import List

from model import Task, File, FileOwnerType, TaskAttachment


def set_task_attachments(request, task_id: int, file_ids: List[int]):
    """
    设置任务附件

    :param request:
    :param task_id:
    :param file_ids:
    :return:
    """

    db = request.app.ctx.db

    with db() as session:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not Task:
            raise ValueError("Task not found.")

        task_class_id = task.class_id

        attachments = session.query(File).where(File.id.in_(file_ids)).all()
        # 所有的文件需要是班级文件
        for attachment in attachments:
            if attachment.owner_type != FileOwnerType.clazz or attachment.owner_clazz_id != task_class_id:
                raise ValueError("File not found.")

        # 移除旧的附件
        session.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).delete()
        for attachment in attachments:
            session.add(TaskAttachment(task_id=task_id, file_id=attachment.id))

        session.commit()

