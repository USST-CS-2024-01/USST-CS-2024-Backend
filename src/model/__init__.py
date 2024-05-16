from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Enum,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

from .enum import *
from .redis import RedisClient

Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, index=True, unique=True)
    password_hash = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True, index=True)
    user_type = Column(
        Enum(UserType, name="user_type"),
        nullable=False,
        index=True,
    )
    account_status = Column(
        Enum(AccountStatus, name="account_status"),
        nullable=False,
        index=True,
    )
    employee_id = Column(String(50), nullable=True, index=True, unique=True)
    name = Column(String(50), nullable=False, index=True)

    __secret_fields__ = ["password_hash"]

    classes = relationship("Class", secondary="class_member", viewonly=True)
    groups = relationship("Group", secondary="class_member", viewonly=True)


class Announcement(Base):
    __tablename__ = "announcement"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    attachment = relationship("File", secondary="announcement_attachment")
    publisher = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    receiver_type = Column(
        Enum(AnnouncementReceiverType, name="receiver_type"),
        nullable=False,
    )
    receiver_class_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    receiver_group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    receiver_user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    receiver_role = Column(
        Enum(UserType, name="user_type"),
        nullable=True,
        index=True,
    )
    read_users = relationship("User", secondary="announcement_read")
    publish_time = Column(DateTime, nullable=False, index=True)

    publisher_user = relationship(
        "User", backref="announcements", foreign_keys="Announcement.publisher"
    )


class AnnouncementRead(Base):
    __tablename__ = "announcement_read"
    announcement_id = Column(Integer, ForeignKey("announcement.id"), primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class AnnouncementAttachment(Base):
    __tablename__ = "announcement_attachment"
    announcement_id = Column(
        Integer,
        ForeignKey("announcement.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class GroupRole(Base):
    __tablename__ = "group_role"
    id = Column(Integer, primary_key=True)
    # 在每个班级中，角色ID是统一的，class_id为1表示这个是作为模板的角色
    class_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    role_name = Column(String(50), nullable=False)  # 角色名称
    role_description = Column(Text, nullable=False)  # 角色描述
    is_manager = Column(Boolean, nullable=False)  # 是否为组长角色


class GroupTask(Base):
    __tablename__ = "group_task"
    id = Column(Integer, primary_key=True)
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=False)
    status = Column(
        Enum(GroupTaskStatus, name="task_status"), nullable=False, index=True
    )
    publisher = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )  # 组内任务以角色区分发布者
    related_files = relationship("File", secondary="group_task_attachment")
    assignees = relationship("GroupRole", secondary="group_task_assignee")
    publish_time = Column(DateTime, nullable=False, index=True)
    deadline = Column(DateTime, nullable=True, index=True)
    update_time = Column(DateTime, nullable=False, index=True)
    priority = Column(Integer, nullable=False, index=True, default=0)  # 优先级


class GroupTaskAttachment(Base):
    __tablename__ = "group_task_attachment"
    task_id = Column(
        Integer,
        ForeignKey("group_task.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class GroupTaskAssignee(Base):
    __tablename__ = "group_task_assignee"
    task_id = Column(
        Integer,
        ForeignKey("group_task.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        Integer,
        ForeignKey("group_role.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class GroupMeeting(Base):
    __tablename__ = "group_meeting"
    id = Column(Integer, primary_key=True)
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    participants = relationship("User", secondary="group_meeting_participant")
    meeting_type = Column(String(50), nullable=False)  # 会议类型: tencent, zoom, etc.
    meeting_link = Column(String(500), nullable=True)  # 会议链接
    meeting_summary_file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    meeting_summary = relationship("File", backref="meeting_summary")
    publisher = Column(
        Integer,
        ForeignKey("group_role.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )


class GroupMeetingParticipant(Base):
    __tablename__ = "group_meeting_participant"
    meeting_id = Column(
        Integer,
        ForeignKey("group_meeting.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class GroupMemberRole(Base):
    __tablename__ = "group_member_role"
    class_member_id = Column(
        Integer,
        ForeignKey("class_member.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        Integer,
        ForeignKey("group_role.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (UniqueConstraint("class_member_id", "role_id"),)
    class_member = relationship(
        "ClassMember", backref="group_member_roles", viewonly=True
    )
    role = relationship("GroupRole", backref="group_member_roles", viewonly=True)


class Group(Base):
    __tablename__ = "group"
    id = Column(Integer, primary_key=True)
    class_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(50), nullable=False, index=True)
    status = Column(Enum(GroupStatus, name="group_status"), nullable=False, index=True)

    members = relationship("ClassMember", backref="group")
    clazz = relationship("Class", backref="groups")

    # 代表了当前组的进度，指向以班级为范围的任务ID
    current_task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )

    current_task = relationship(
        "Task", backref="group", foreign_keys="Group.current_task_id"
    )


class File(Base):
    __tablename__ = "file"
    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False, index=True)
    file_key = Column(String(1000), nullable=False)
    file_type = Column(Enum(FileType, name="file_type"), nullable=False, index=True)
    file_size = Column(Integer, nullable=False, index=True)
    owner_type = Column(
        # 文件的拥有者类型，可以是作业、小组、个人
        Enum(FileOwnerType, name="owner_type"),
        nullable=False,
    )
    owner_delivery_id = Column(
        Integer,
        ForeignKey("delivery.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="NO ACTION", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_clazz_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    create_date = Column(DateTime, nullable=False, index=True)
    modify_date = Column(DateTime, nullable=False, index=True)
    tags = Column(JSON, nullable=True)


class Class(Base):
    __tablename__ = "class"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    # 指向班级范围任务的第一个任务ID，用于设置班级任务的顺序
    first_task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    task_list = relationship("Task", backref="class", foreign_keys="Task.class_id")
    status = Column(
        Enum(ClassStatus, name="class_status"),
        nullable=False,
        index=True,
    )

    members = relationship("User", secondary="class_member", viewonly=True)
    roles = relationship("GroupRole", backref="class_")


class ClassMember(Base):
    __tablename__ = "class_member"
    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
    )
    is_teacher = Column(Boolean, nullable=False, index=True)
    repo_usernames = Column(JSON, nullable=True, default=[])
    status = Column(
        Enum(GroupMemberRoleStatus, name="member_role_status"),
        nullable=True,
        index=True,
    )

    roles = relationship("GroupRole", secondary="group_member_role")

    user = relationship("User", backref="class_member")
    class_ = relationship("Class", backref="class_member")

    # Indexes
    __table_args__ = (UniqueConstraint("user_id", "class_id"),)


class Task(Base):
    __tablename__ = "task"
    id = Column(Integer, primary_key=True)
    class_id = Column(
        Integer,
        ForeignKey("class.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(500), nullable=False, index=True)
    content = Column(Text, nullable=False)
    specified_role = Column(
        Integer,
        ForeignKey("group_role.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    attached_files = relationship("File", secondary="task_attachment")
    publish_time = Column(DateTime, nullable=False, index=True)
    deadline = Column(DateTime, nullable=False, index=True)
    grade_percentage = Column(Float, nullable=False)
    next_task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )

    role = relationship(
        "GroupRole", backref="tasks", foreign_keys="Task.specified_role"
    )


class TaskAttachment(Base):
    __tablename__ = "task_attachment"
    task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )


class RepoRecord(Base):
    __tablename__ = "repo_record"
    id = Column(Integer, primary_key=True)
    status = Column(
        Enum(RepoRecordStatus, name="record_status"),
        nullable=False,
        index=True,
    )
    repo_url = Column(String(1000), nullable=False)
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_stats = Column(JSON, nullable=True)
    code_line_stats = Column(JSON, nullable=True)
    create_time = Column(DateTime, nullable=False, index=True)
    stat_time = Column(DateTime, nullable=True, index=True)
    user_repo_mapping = Column(JSON, nullable=True)
    archive_file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    archive = relationship("File", backref="repo_records")


class DeliveryItem(Base):
    __tablename__ = "delivery_item"
    id = Column(Integer, primary_key=True)
    item_type = Column(Enum(DeliveryType, name="item_type"), nullable=False, index=True)
    item_file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    item_repo_id = Column(
        Integer,
        ForeignKey("repo_record.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    delivery_id = Column(
        Integer,
        ForeignKey("delivery.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    file = relationship("File", backref="delivery_items")
    repo = relationship("RepoRecord", backref="delivery_items")

    # Indexes
    __table_args__ = (UniqueConstraint("item_type", "item_file_id", "item_repo_id"),)


# 每组的每个任务都会有组长和组员的互相评分记录
class TaskGroupMemberScore(Base):
    __tablename__ = "task_group_member_score"
    task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    # 组长的评分来自于小组其他成员
    group_manager_score = Column(JSON, nullable=False)
    # 组员的评分来自于组长
    group_member_scores = Column(JSON, nullable=False)


class Delivery(Base):
    __tablename__ = "delivery"
    id = Column(Integer, primary_key=True)
    delivery_items = relationship("DeliveryItem", backref="delivery")
    task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id = Column(
        Integer,
        ForeignKey("group.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    delivery_user = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    delivery_time = Column(DateTime, nullable=False, index=True)
    delivery_status = Column(
        Enum(
            DeliveryStatus,
            name="delivery_status",
        ),
        nullable=False,
        index=True,
    )
    delivery_comments = Column(Text, nullable=True)
    comment_time = Column(DateTime, nullable=True, index=True)
    task_grade_percentage = Column(Float, nullable=False, index=True)

    task = relationship("Task", backref="deliveries")


class AIDocScoreRecord(Base):
    __tablename__ = "ai_doc_score_record"
    id = Column(Integer, primary_key=True)
    file_id = Column(
        Integer,
        ForeignKey("file.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(AIDocStatus, name="score_status"),
        nullable=False,
        index=True,
    )
    create_time = Column(DateTime, nullable=False, index=True)
    score_time = Column(DateTime, nullable=True, index=True)
    doc_evaluation = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)


class TeacherScore(Base):
    __tablename__ = "teacher_score"
    task_id = Column(
        Integer,
        ForeignKey("task.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    score = Column(Float, nullable=False)
    score_time = Column(DateTime, nullable=False, index=True)
    score_details = Column(JSON, nullable=True)

    user = relationship("User", backref="teacher_scores")
    task = relationship("Task", backref="teacher_scores")


class Log(Base):
    __tablename__ = "log"
    id = Column(Integer, primary_key=True)
    log_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="NO ACTION", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    user_name = Column(String(50), nullable=False, index=True)
    user_employee_id = Column(String(50), nullable=True, index=True)
    user_type = Column(
        Enum(UserType, name="user_type"),
        nullable=False,
        index=True,
    )
    operation_time = Column(DateTime, nullable=False, index=True)
    operation_ip = Column(String(50), nullable=False, index=True)


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    update_time = Column(DateTime, nullable=False, index=True)
