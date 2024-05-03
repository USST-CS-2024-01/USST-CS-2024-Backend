from sqlalchemy import select, and_, or_

import service.task
from model import Class, UserType, GroupRole, Task, ClassStatus


def has_class_access(request, class_id: int) -> Class or bool:
    """
    Check whether the user has access to the class
    :param request: Request
    :param class_id: Class ID
    :return: Whether the user has access to the class
    """
    user = request.ctx.user
    db = request.app.ctx.db
    stmt = select(Class).where(
        and_(
            Class.id == class_id,
            or_(
                Class.members.any(id=user.id),
                user.user_type == UserType.admin,
            ),
        )
    )

    with db() as session:
        result = session.execute(stmt).scalar()
        return result if result else False


def generate_new_class(db, class_name: str, class_description: str = None) -> Class:
    """
    Generate a new class
    :param db: Database session
    :param class_name: Class name
    :param class_description
    :return: New class
    """

    # 模板班级角色ID与新班级角色ID的映射
    role_map = {}

    with db() as session:
        stmt_template_class = select(Class).where(Class.id == 1)
        template_class = session.execute(stmt_template_class).scalar()
        if not template_class:
            raise ValueError("Template class not found.")

        if class_description is None:
            class_description = template_class.description

        # 获取课程模板班级的角色列表
        stmt_template_roles = session.query(GroupRole).filter(
            GroupRole.class_id == template_class.id
        )
        template_roles = stmt_template_roles.all()

        # 获取课程模板班级的任务列表
        stmt_template_tasks = session.query(Task).filter(
            Task.class_id == template_class.id
        )
        template_tasks = stmt_template_tasks.all()

        # 创建新班级
        new_class = Class(
            name=class_name,
            description=class_description,
            status=ClassStatus.not_started,
        )
        session.add(new_class)

        session.flush()  # 刷新数据库，获取新班级的ID

        # 创建新班级的角色
        new_roles = []
        for role in template_roles:
            new_role = GroupRole(
                role_name=role.role_name,
                role_description=role.role_description,
                is_manager=role.is_manager,
                class_id=new_class.id,
            )
            session.add(new_role)
            new_roles.append(new_role)

        session.flush()  # 刷新数据库，获取新角色的ID

        # 设置映射关系
        for role in template_roles:
            role_map[role.id] = new_roles[template_roles.index(role)].id

        # 创建新班级的任务
        new_tasks = []
        for task in template_tasks:
            new_task = Task(
                class_id=new_class.id,
                name=task.name,
                content=task.content,
                publish_time=task.publish_time,
                deadline=task.deadline,
                grade_percentage=task.grade_percentage,
            )
            # TODO 创建任务时，若存在附件，则需要先创建该附件的副本，并将副本添加到新任务的附件列表中
            new_task.specified_role = role_map[task.specified_role]
            session.add(new_task)
            new_tasks.append(new_task)

        session.flush()  # 刷新数据库，获取新任务的ID

        # 更新新班级的第一个任务ID，依次更新新班级的任务列表
        for i, task in enumerate(new_tasks):
            if task.id is None:
                raise ValueError("Task ID is None.")
            if i == 0:
                new_class.first_task_id = task.id
            if i < len(new_tasks) - 1:
                task.next_task_id = new_tasks[i + 1].id

        session.commit()
        session.refresh(new_class)

        return new_class


def change_class_task_sequence(request, class_id: int, task_id_list: list[int]) -> None:
    """
    Change the sequence of tasks in a class
    :param request: Request
    :param class_id: Class ID
    :param task_id_list: Task ID list
    :return: Whether the operation is successful
    """
    db = request.app.ctx.db
    # task_id_list中不能存在重复的task_id
    if len(task_id_list) != len(set(task_id_list)):
        raise ValueError("Task ID list contains duplicates.")

    # 获取班级中被锁定的任务
    locked_tasks = service.task.get_locked_tasks(request, class_id, nocheck=True)

    with db() as session:
        stmt_class = select(Class).where(Class.id == class_id)
        target_class = session.execute(stmt_class).scalar()
        if not target_class:
            raise ValueError("Class not found.")

        # 获取班级的所有任务
        stmt_tasks = session.query(Task).filter(Task.class_id == class_id)
        all_tasks = stmt_tasks.all()
        if len(all_tasks) != len(task_id_list):
            raise ValueError("Task count mismatch.")

        # 检查task_id_list中的task_id是否都属于该班级
        for task_id in task_id_list:
            if task_id not in [task.id for task in all_tasks]:
                raise ValueError("Task ID not found in class.")

        all_tasks.sort(key=lambda x: task_id_list.index(x.id))

        # 更新任务的next_task_id
        for i, task_id in enumerate(task_id_list):
            if i < len(task_id_list) - 1:
                all_tasks[i].next_task_id = task_id_list[i + 1]
            else:
                all_tasks[i].next_task_id = None

        # 更新班级的first_task_id
        target_class.first_task_id = task_id_list[0]

        # 检查修改后的任务链中，前面部分是否与已锁定的任务连完全相同
        for i, task in enumerate(locked_tasks):
            if task.id != task_id_list[i]:
                raise ValueError("已经锁定的任务顺序无法调整。")

        session.commit()


if __name__ == "__main__":
    from sqlalchemy import engine
    from sqlalchemy.orm import sessionmaker

    engine = engine.create_engine(
        "mysql+pymysql://root:password@localhost:3306/scs_backend"
    )
    session_factory = sessionmaker(bind=engine)

    # print(generate_new_class(session_factory, "测试课程", "课程描述"))
    change_class_task_sequence(session_factory, 2, [8, 9, 10, 11, 12, 13, 14])
