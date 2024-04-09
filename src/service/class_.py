from sqlalchemy import select, and_, or_

from model import Class, UserType, GroupRole, Task, ClassStatus


def has_class_access(request, class_id: int) -> bool:
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
        result = session.execute(stmt)
        return result.scalar() is not None


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
        print("Template class found.")

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
                attached_files=[],
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

        return new_class


if __name__ == "__main__":
    from sqlalchemy import engine
    from sqlalchemy.orm import sessionmaker

    engine = engine.create_engine(
        "mysql+pymysql://root:password@localhost:3306/scs_backend"
    )
    session_factory = sessionmaker(bind=engine)

    print(generate_new_class(session_factory, "测试课程", "课程描述"))
