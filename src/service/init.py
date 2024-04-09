from os import name

from sqlalchemy import desc
from model import Class, User
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
        description="""（1）软件产业经历了从软件作坊生产向大规模工业生产的转变。\n（2）随着软件规模与复杂性的不断增加，目前软件开发多以团队方式开展，这就要求软件从业人员除了具备专业知识与技术以外，还要求具有团队协作能力、项目组织与管理能力、应用软件过程改进的能力、交流沟通能力、文档写作表达能力等。\n（3）目前计算机专业课程都是从不同的知识与技能角度对学生进行培养，需要通过一个课程项目把这些知识点纵向贯穿起来。\n（4）企业项目开发中需要的诸多软能力，如团队协作能力、交流展示能力、文档撰写及过程管理与改进等能力的培养都存在明显不足。""",
        status=ClassStatus.not_started,
    )

    with db() as db:
        if not db.query(User).filter(User.id == 1).first():
            db.add(stmt_create_admin_user)
            db.commit()

        if not db.query(Class).filter(Class.id == 1).first():
            db.add(stmt_create_template_class)
            db.commit()
