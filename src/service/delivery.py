from sqlalchemy import select, and_

import service.group
import service.task
from model import (
    Delivery,
    DeliveryStatus,
    Group,
    TaskGroupMemberScore,
    ClassStatus,
    ClassMember,
    Task,
    TeacherScore,
)


def get_task_latest_delivery(
    request, task_id: int, group_id: int
) -> (Delivery or bool):
    """
    Get the latest delivery of the task

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID

    :return: Delivery
    """
    db = request.app.ctx.db

    stmt = (
        select(Delivery)
        .where(
            and_(
                Delivery.task_id == task_id,
                Delivery.group_id == group_id,
                Delivery.delivery_status != DeliveryStatus.draft,
            )
        )
        .order_by(Delivery.delivery_time.desc())
        .limit(1)
    )

    with db() as session:
        delivery = session.execute(stmt).scalar()
        return delivery


def check_task_score_finished(request, task_id: int, group_id: int) -> bool:
    """
    Check whether the task score is finished

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID

    :return: Whether the task score is finished
    """
    db = request.app.ctx.db
    with db() as session:
        stmt = select(Group).where(Group.id.__eq__(group_id))
        group = session.execute(stmt).scalar()
        if not group:
            raise ValueError("Group not found")

        member_ids = [member.user_id for member in group.members]
        leader = service.group.get_group_manager_user_id(
            request, group.class_id, group_id
        )
        member_ids.remove(leader)
        member_ids = [str(i) for i in member_ids]

        stmt = select(TaskGroupMemberScore).where(
            and_(
                TaskGroupMemberScore.task_id == task_id,
                TaskGroupMemberScore.group_id == group_id,
            )
        )
        scores: TaskGroupMemberScore = session.execute(stmt).scalar()
        if not scores:
            return False

        member_idset = set(member_ids)
        for k, v in scores.group_member_scores.items():
            if k not in member_idset:
                return False
            member_idset.remove(k)
            if v <= 0 or v > 100:
                return False

        if member_idset:
            return False

        member_idset = set(member_ids)
        for k, v in scores.group_manager_score.items():
            if k not in member_idset:
                return False
            member_idset.remove(k)
            if v <= 0 or v > 100:
                return False

        if member_idset:
            return False

        return True


def check_can_create_delivery(request, task_id: int, group_id: int) -> bool:
    """
    Check whether the user can create a new delivery

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID

    :return: Whether the user can create a new delivery
    """
    db = request.app.ctx.db

    with db() as session:
        stmt = select(Group).where(Group.id.__eq__(group_id))
        group = session.execute(stmt).scalar()
        locked_tasks = [
            x.id
            for x in service.task.get_group_locked_tasks(
                request, group.class_id, group_id
            )
        ]
        session.add(group)

        if not group:
            raise ValueError("小组不存在")
        if group.clazz.status != ClassStatus.teaching:
            raise ValueError("班级不在教学状态，无法提交任务")
        if group.current_task_id not in locked_tasks:
            raise ValueError("请勿超越当前任务提交任务")

    latest_delivery: Delivery = get_task_latest_delivery(request, task_id, group_id)
    if latest_delivery:
        if latest_delivery.delivery_status not in [
            DeliveryStatus.leader_rejected,
            DeliveryStatus.teacher_rejected,
        ]:
            raise ValueError("提交的内容正在审核中或者已经通过，无法提交新的内容")

    if not check_task_score_finished(request, task_id, group_id):
        raise ValueError("任务评分未完成，无法提交任务")

    return True


def get_task_draft(request, task_id: int, group_id: int) -> (Delivery or bool):
    """
    Get the draft of the task

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID

    :return: Delivery
    """
    db = request.app.ctx.db

    stmt = (
        select(Delivery)
        .where(
            and_(
                Delivery.task_id == task_id,
                Delivery.group_id == group_id,
                Delivery.delivery_status == DeliveryStatus.draft,
            )
        )
        .order_by(Delivery.delivery_time.desc())
        .limit(1)
    )

    with db() as session:
        delivery = session.execute(stmt).scalar()
        if not delivery:
            raise ValueError("未找到草稿")
        return delivery


def check_can_create_draft(
    request, task_id: int, class_id: int, group_id: int
) -> (Group, ClassMember, bool, Task):
    """
    Check whether the user can create a draft

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID
    :param class_id: Class ID

    :return: Group; ClassMember; Whether the user is group leader; Current task
    """
    db = request.app.ctx.db

    with db() as session:
        group, class_member, is_manager = service.group.have_group_access(
            request, class_id=class_id, group_id=group_id
        )
        if not group:
            raise ValueError("You don't have the permission to access the group.")

        locked_tasks = [
            x.id
            for x in service.task.get_group_locked_tasks(
                request, group.class_id, group_id
            )
        ]
        session.add(group)

        if group.clazz.status != ClassStatus.teaching:
            raise ValueError("班级不在教学状态，无法创建草稿")
        if group.current_task_id not in locked_tasks:
            raise ValueError("请勿超越当前任务创建草稿")

        latest_delivery = get_task_latest_delivery(request, task_id, group_id)
        if latest_delivery:
            if latest_delivery.delivery_status not in [
                DeliveryStatus.leader_rejected,
                DeliveryStatus.teacher_rejected,
            ]:
                raise ValueError("提交的内容正在审核中或者已经通过，无法创建草稿")

        current_task = service.task.get_current_task(request, group_id)

        if not class_member:
            raise ValueError("您不是该小组成员")

        session.add(class_member)
        if (
            current_task.specified_role not in [r.id for r in class_member.roles]
            and not is_manager
        ):
            raise ValueError("您没有权限提交该任务的交付物")

    return group, class_member, is_manager, current_task


def get_group_task_score(
    request, task_id: int, group_id: int
) -> (TeacherScore or bool):
    """
    Get the score of the task

    :param request: Request
    :param task_id: Task ID
    :param group_id: Group ID

    :return: TaskGroupMemberScore
    """
    db = request.app.ctx.db

    with db() as session:
        stmt = select(ClassMember.user_id).where(
            and_(
                ClassMember.group_id == group_id,
                ClassMember.is_teacher.is_(False),
            )
        )
        member_ids = session.execute(stmt).scalars().all()
        if not member_ids:
            raise ValueError("小组成员为空")

        stmt = select(TeacherScore).where(
            and_(
                TeacherScore.task_id == task_id,
                TeacherScore.user_id.in_(member_ids),
            )
        )
        score_list = session.execute(stmt).scalars().all()

        member_ids_set = set(member_ids)
        for item in score_list:
            member_ids_set.remove(item.user_id)

        if member_ids_set:
            return score_list, False
        return score_list, True
