# _*_ coding: utf-8 _*_
"""
Time:     2024/4/16 15:13
Author:   不做评论(vvbbnn00)
Version:  
File:     task.py
Describe: 
"""
from typing import List

from model import Task, File, FileOwnerType, TaskAttachment, Class, Group


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
            if (
                attachment.owner_type != FileOwnerType.clazz
                or attachment.owner_clazz_id != task_class_id
            ):
                raise ValueError("File not found.")

        # 移除旧的附件
        session.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).delete()
        for attachment in attachments:
            session.add(TaskAttachment(task_id=task_id, file_id=attachment.id))

        session.commit()


def check_task_chain(request, class_id) -> List[Task]:
    """
    检查任务链

    :param request:
    :param class_id:
    :return:
    """
    db = request.app.ctx.db

    task_chain = []

    with db() as session:
        tasks = session.query(Task).filter(Task.class_id == class_id).all()
        task_map = {task.id: task for task in tasks}

        first_task_id = (
            session.query(Class.first_task_id).filter(Class.id == class_id).scalar()
        )
        if not first_task_id:
            raise ValueError("First task not found.")
        first_task = task_map.pop(first_task_id, None)  # 使用pop方法删除字典中的元素
        if not first_task:
            raise ValueError("First task not found.")
        next_task_id = first_task.next_task_id

        cnt = 0

        while next_task_id and cnt < len(tasks):
            task = task_map.pop(next_task_id, None)
            if not task:
                raise ValueError("Task not found.")

            task_chain.append(task)
            next_task_id = task.next_task_id
            cnt += 1

        if cnt != len(tasks) - 1:
            raise ValueError("Task chain is not complete.")

    return tasks


def get_locked_tasks(request, class_id: int) -> List[Task]:
    """
    获取班级中，所有被锁定的任务（锁定的任务指班级中的某一个小组
    已经到达了该任务状态，因此在该任务之前的所有任务[包括该任务]
    无法被删除和调换顺序）

    :param request:
    :param class_id:
    :return:
    """

    task_chain = check_task_chain(request, class_id)
    locked_tasks = []

    with request.app.ctx.db() as session:
        group_task_ids = (
            session.query(Group.current_task_id)
            .filter(Group.class_id == class_id)
            .all()
        )

        group_task_ids = [task_id for task_id, in group_task_ids if task_id]

        # 从TaskChain的末端开始，向前遍历，直到遇到第一个被锁定的任务
        last_locked_task = None
        for task in reversed(task_chain):
            if task.id in group_task_ids:
                last_locked_task = task
                break

        # 从TaskChain的开端开始，向后遍历，直到遇到第一个被锁定的任务
        if last_locked_task:
            for task in task_chain:
                locked_tasks.append(task)
                if task.id == last_locked_task.id:
                    break

    return locked_tasks


def get_group_locked_tasks(request, class_id: int, group_id: int) -> List[Task]:
    """
    获取班级中，某一个小组锁定的任务（锁定的任务指该小组已经到达了该任务状态，
    因此在该任务之前的所有任务[包括该任务]无法被删除和调换顺序）

    :param request:
    :param class_id:
    :param group_id:
    :return:
    """

    task_chain = check_task_chain(request, class_id)
    locked_tasks = []

    with request.app.ctx.db() as session:
        group = session.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise ValueError("Group not found.")
        if group.class_id != class_id:
            raise ValueError("Group not in class.")

        group_task_id = group.current_task_id
        if not group_task_id:
            return locked_tasks

        group_task = session.query(Task).filter(Task.id == group_task_id).first()
        if not group_task:
            raise ValueError("Group task not found.")

        # 从TaskChain的末端开始，向前遍历，直到遇到第一个被锁定的任务
        last_locked_task = None
        for task in reversed(task_chain):
            if task.id == group_task_id:
                last_locked_task = task
                break

        # 从TaskChain的开端开始，向后遍历，直到遇到第一个被锁定的任务
        if last_locked_task:
            for task in task_chain:
                locked_tasks.append(task)
                if task.id == last_locked_task.id:
                    break

    return locked_tasks
