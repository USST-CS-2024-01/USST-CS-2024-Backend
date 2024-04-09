import util.string
from model import Class, User, Task, GroupRole
from model.enum import AccountStatus, ClassStatus, UserType
from util import encrypt


def database_init(db):
    """
    Initialize the database with the default data.

    :param db: The database session.
    """
    stmt_create_admin_user = User(
        id=1,
        username="admin",
        password_hash=encrypt.bcrypt_hash("admin"),
        user_type=UserType.admin,
        account_status=AccountStatus.active,
        employee_id="admin",
        name="admin",
    )

    stmt_create_template_class = Class(
        id=1,
        name="课程模板",
        description="""（1）软件产业经历了从软件作坊生产向大规模工业生产的转变。
（2）随着软件规模与复杂性的不断增加，目前软件开发多以团队方式开展，这就要求软件从业人员除了具备专业知识与技术以外，
还要求具有团队协作能力、项目组织与管理能力、应用软件过程改进的能力、交流沟通能力、文档写作表达能力等。
（3）目前计算机专业课程都是从不同的知识与技能角度对学生进行培养，需要通过一个课程项目把这些知识点纵向贯穿起来。
（4）企业项目开发中需要的诸多软能力，如团队协作能力、交流展示能力、文档撰写及过程管理与改进等能力的培养都存在明显不足。
""",
        status=ClassStatus.not_started,
    )

    role_list = [
        GroupRole(
            id=1,
            role_name="组长",
            role_description="负责统筹组内工作，协调组内成员，负责组内任务分配与进度跟踪，负责组内成员的工作质量与工作效率。",
            is_manager=True,
        ),
        GroupRole(
            id=2,
            role_name="产品经理",
            role_description="软件项目的需求分析",
            is_manager=False,
        ),
        GroupRole(
            id=3,
            role_name="开发经理",
            role_description="全面负责，重点负责项目的设计及实施",
            is_manager=False,
        ),
        GroupRole(
            id=4,
            role_name="计划经理",
            role_description="项目各个计划的制定及监控",
            is_manager=False,
        ),
        GroupRole(
            id=5,
            role_name="质量经理",
            role_description="项目质量计划的指定及质量的控制",
            is_manager=False,
        ),
        GroupRole(
            id=6,
            role_name="测试经理",
            role_description="测试计划的制定及项目的测试",
            is_manager=False,
        ),
    ]

    task_list = [
        Task(
            id=1,
            class_id=1,
            name="项目启动",
            specified_role=2,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=10,
            content="""
## 任务目标
- 建立项目团队、成员角色
- 确立项目的范围

## 交付物
- 项目范围报告（doc格式）
""",
        ),
        Task(
            id=2,
            class_id=1,
            name="项目计划",
            specified_role=4,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=10,
            content="""
## 任务目标
- 完成进度计划
- 完成测试计划 
- 完成产品质量计划

## 交付物
- 项目进度计划（doc格式）
- 项目测试计划（doc格式）
- 项目质量计划（doc格式）
""",
        ),
        Task(
            id=3,
            class_id=1,
            name="项目需求",
            specified_role=2,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=20,
            content="""
## 任务目标
- 与教师交流，确定产品的详细需求
- 撰写支持材料与文档

## 交付物
- 产品需求文档（doc格式）
""",
        ),
        Task(
            id=4,
            class_id=1,
            name="项目设计",
            specified_role=3,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=20,
            content="""
## 任务目标
- 完成产品的总体功能设计
- 完成产品的详细设计
- 完成设计审查
- 撰写设计报告

## 交付物
- 产品总体设计报告（doc格式）
""",
        ),
        Task(
            id=5,
            class_id=1,
            name="项目实施",
            specified_role=3,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=20,
            content="""
## 任务目标
- 完成编码
- 完成代码审查并记录审查结果

## 交付物
- 代码（Github仓库链接）
- 代码审查报告（doc格式）
""",
        ),
        Task(
            id=6,
            class_id=1,
            name="项目测试",
            specified_role=6,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=10,
            content="""
## 任务目标
- 完成单元测试并记录测试数据
- 完成集成与系统测试
- 分析测试结果

## 交付物
- 测试数据（doc格式）
- 测试报告（doc格式）
""",
        ),
        Task(
            id=7,
            class_id=1,
            name="项目审查",
            specified_role=5,
            publish_time=util.string.timestamp_to_datetime(0),
            deadline=util.string.timestamp_to_datetime(0),
            grade_percentage=10,
            content="""
## 任务目标
- 审查报告
- 审查系统
- 完成团队与成员角色评估

## 交付物
- 审查报告（doc格式）
""",
        ),
    ]

    with db() as db:
        if not db.query(User).filter(User.id == 1).first():
            db.add(stmt_create_admin_user)
            db.commit()

        if not db.query(Class).filter(Class.id == 1).first():
            db.add(stmt_create_template_class)
            db.commit()
        else:
            return

        for role in role_list:
            role.class_id = 1
            db.add(role)
        db.commit()

        for task in task_list:
            db.add(task)
        db.commit()

        for i in range(len(task_list) - 1):
            task_list[i].next_task_id = task_list[i + 1].id

        stmt_create_template_class.first_task_id = task_list[0].id
        db.commit()
