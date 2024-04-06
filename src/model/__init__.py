import enum

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Enum,
    ForeignKeyConstraint,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class JsonableEnum(enum.Enum):
    def to_json(self):
        return self.value

    @classmethod
    def from_json(cls, value):
        return cls(value)


class UserType(JsonableEnum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class AccountStatus(JsonableEnum):
    active = "active"
    inactive = "inactive"
    locked = "locked"


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


class AnnouncementReceiverType(JsonableEnum):
    all = "all"
    class_ = "class"
    group = "group"
    individual = "individual"


class Announcement(Base):
    __tablename__ = "announcement"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    attachment = relationship("File", secondary="announcement_attachment")
    publisher = Column(Integer, ForeignKey("user.id"), nullable=False)
    receiver_type = Column(
        Enum(AnnouncementReceiverType, name="receiver_type"),
        nullable=False,
    )
    receiver_class_id = Column(
        Integer, ForeignKey("class.id"), nullable=True, index=True
    )
    receiver_group_id = Column(
        Integer, ForeignKey("group.id"), nullable=True, index=True
    )
    receiver_user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    read_users = relationship("User", secondary="announcement_read")
    publish_time = Column(DateTime, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["publisher"],
            ["user.id"],
            name="fk_announcement_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["receiver_class_id"],
            ["class.id"],
            name="fk_announcement_class",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["receiver_group_id"],
            ["group.id"],
            name="fk_announcement_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["receiver_user_id"],
            ["user.id"],
            name="fk_announcement_receiver_user",
            ondelete="CASCADE",
        ),
    )


class AnnouncementRead(Base):
    __tablename__ = "announcement_read"
    announcement_id = Column(Integer, ForeignKey("announcement.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    read_time = Column(DateTime, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["announcement_id"],
            ["announcement.id"],
            name="fk__announcement_read_announcement",
            ondelete="CASCADE",
        ),
    )


class AnnouncementAttachment(Base):
    __tablename__ = "announcement_attachment"
    announcement_id = Column(Integer, ForeignKey("announcement.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("file.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["announcement_id"],
            ["announcement.id"],
            name="fk_announcement_attachment_announcement",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id"], ["file.id"], name="fk_file", ondelete="CASCADE"
        ),
    )


class GroupRole(Base):
    __tablename__ = "group_role"
    id = Column(Integer, primary_key=True)
    # 在每个班级中，角色ID是统一的，class_id为0表示这个是作为模板的角色
    class_id = Column(Integer, ForeignKey("class.id"), nullable=False)
    role_name = Column(String(50), nullable=False)  # 角色名称
    role_description = Column(Text, nullable=False)  # 角色描述

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_id"],
            ["class.id"],
            name="fk_group_role_class",
            ondelete="CASCADE",
        ),
    )


class GroupTaskType(JsonableEnum):
    group = "group"
    individual = "individual"


class GroupTask(Base):
    __tablename__ = "group_task"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("group.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=False)
    status = Column(Enum(GroupTaskType, name="task_status"), nullable=False, index=True)
    related_files = relationship("File", secondary="group_task_attachment")
    publisher = Column(
        Integer, ForeignKey("group_role.id"), nullable=False
    )  # 组内任务以角色区分发布者
    assignees = relationship("GroupRole", secondary="group_task_assignee")
    publish_time = Column(DateTime, nullable=False, index=True)
    deadline = Column(DateTime, nullable=False, index=True)
    update_time = Column(DateTime, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
            name="fk_group_task_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["publisher"],
            ["group_role.id"],
            name="fk_group_task_role",
            ondelete="CASCADE",
        ),
    )


class GroupTaskAttachment(Base):
    __tablename__ = "group_task_attachment"
    task_id = Column(Integer, ForeignKey("group_task.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("file.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"],
            ["group_task.id"],
            name="fk_group_task_attachment_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id"],
            ["file.id"],
            name="fk_group_task_attachment_file",
            ondelete="CASCADE",
        ),
    )


class GroupTaskAssignee(Base):
    __tablename__ = "group_task_assignee"
    task_id = Column(Integer, ForeignKey("group_task.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("group_role.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"],
            ["group_task.id"],
            name="fk_group_task_assignee_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id"],
            ["group_role.id"],
            name="fk_group_task_assignee_role",
            ondelete="CASCADE",
        ),
    )


class GroupMeeting(Base):
    __tablename__ = "group_meeting"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("group.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    participants = relationship("User", secondary="group_meeting_participant")
    meeting_type = Column(String(50), nullable=False)  # 会议类型: tencent, zoom, etc.
    meeting_link = Column(String(500), nullable=True)  # 会议链接
    related_files = relationship("File", secondary="group_meeting_attachment")

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
            name="fk_group_meeting_group",
            ondelete="CASCADE",
        ),
    )


class GroupMeetingParticipant(Base):
    __tablename__ = "group_meeting_participant"
    meeting_id = Column(Integer, ForeignKey("group_meeting.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id"],
            ["group_meeting.id"],
            name="fk_group_meeting_participant_meeting",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_group_meeting_participant_user",
            ondelete="CASCADE",
        ),
    )


class GroupMeetingAttachment(Base):
    __tablename__ = "group_meeting_attachment"
    meeting_id = Column(Integer, ForeignKey("group_meeting.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("file.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["meeting_id"],
            ["group_meeting.id"],
            name="fk_group_meeting_attachment_meeting",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id"],
            ["file.id"],
            name="fk_group_meeting_attachment_file",
            ondelete="CASCADE",
        ),
    )


class GroupMember(Base):
    __tablename__ = "group_member"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    group_id = Column(Integer, ForeignKey("group.id"))
    roles = relationship("GroupRole", secondary="group_member_role")
    repo_usernames = Column(JSON, nullable=True, default={})

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_group_member_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
            name="fk_group_member_group",
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "group_id"),
    )


class GroupMemberRole(Base):
    __tablename__ = "group_member_role"
    group_member_id = Column(Integer, ForeignKey("group_member.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("group_role.id"))

    __table_args__ = (
        ForeignKeyConstraint(
            ["group_member_id"],
            ["group_member.id"],
            name="fk_group_member_role_member",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["role_id"],
            ["group_role.id"],
            name="fk_group_member_role_role",
            ondelete="CASCADE",
        ),
        UniqueConstraint("group_member_id", "role_id"),
    )


class GroupStatus(JsonableEnum):
    pending = "pending"
    normal = "normal"


class Group(Base):
    __tablename__ = "group"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("class.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False, index=True)
    status = Column(Enum(GroupStatus, name="group_status"), nullable=False, index=True)
    # 代表了当前组的进度，指向以班级为范围的任务ID
    current_task_id = Column(Integer, ForeignKey("task.id"), nullable=True, index=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_id"],
            ["class.id"],
            name="fk_group_class",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["current_task_id"],
            ["group_task.id"],
            name="fk_group_task",
            ondelete="CASCADE",
        ),
    )


class FileType(JsonableEnum):
    document = "document"
    other = "other"


class FileOwnerType(JsonableEnum):
    delivery = "delivery"
    group = "group"
    user = "user"


class File(Base):
    __tablename__ = "file"
    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False, index=True)
    file_type = Column(Enum(FileType, name="file_type"), nullable=False, index=True)
    file_size = Column(Integer, nullable=False, index=True)
    owner_type = Column(
        # 文件的拥有者类型，可以是作业、小组、个人
        Enum(FileOwnerType, name="owner_type"),
        nullable=False,
    )
    owner_delivery_id = Column(
        Integer, ForeignKey("delivery.id"), nullable=True, index=True
    )
    owner_group_id = Column(Integer, ForeignKey("group.id"), nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
    create_date = Column(DateTime, nullable=False, index=True)
    modify_date = Column(DateTime, nullable=False, index=True)
    tags = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_delivery_id"],
            ["delivery.id"],
            name="fk_file_delivery",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_group_id"],
            ["group.id"],
            name="fk_file_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["owner_user_id"],
            ["user.id"],
            name="fk_file_user",
            ondelete="CASCADE",
        ),
    )


class ClassStatus(JsonableEnum):
    not_started = "not_started"
    grouping = "grouping"
    teaching = "teaching"
    finished = "finished"


class Class(Base):
    __tablename__ = "class"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    # 指向班级范围任务的第一个任务ID，用于设置班级任务的顺序
    first_task_id = Column(Integer, ForeignKey("task.id"), nullable=True)
    task_list = relationship("Task", backref="class", foreign_keys="Task.class_id")
    status = Column(
        Enum(ClassStatus, name="class_status"),
        nullable=False,
        index=True,
    )

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["first_task_id"],
            ["task.id"],
            name="fk_class_task",
            ondelete="SET NULL",
        ),
    )


class Task(Base):
    __tablename__ = "task"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("class.id"), nullable=True, index=True)
    name = Column(String(500), nullable=False, index=True)
    content = Column(Text, nullable=False)
    specified_role = Column(Integer, ForeignKey("group_role.id"), nullable=True)
    attached_files = relationship("File", secondary="task_attachment")
    publish_time = Column(DateTime, nullable=False, index=True)
    deadline = Column(DateTime, nullable=False, index=True)
    grade_percentage = Column(Float, nullable=False)
    next_task_id = Column(Integer, ForeignKey("task.id"), nullable=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_id"],
            ["class.id"],
            name="fk_task_class",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["specified_role"],
            ["group_role.id"],
            name="fk_task_role",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["next_task_id"],
            ["task.id"],
            name="fk_task_next_task",
            ondelete="SET NULL",
        ),
    )


class TaskAttachment(Base):
    __tablename__ = "task_attachment"
    task_id = Column(Integer, ForeignKey("task.id"), primary_key=True)
    file_id = Column(Integer, ForeignKey("file.id"), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name="fk_task_attachment_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["file_id"], ["file.id"], name="fk_task_attachment_file", ondelete="CASCADE"
        ),
    )


class RepoRecordStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class RepoRecord(Base):
    __tablename__ = "repo_record"
    id = Column(Integer, primary_key=True)
    status = Column(
        Enum(RepoRecordStatus, name="record_status"),
        nullable=False,
        index=True,
    )
    repo_url = Column(String(1000), nullable=False)
    group_id = Column(Integer, ForeignKey("group.id"), nullable=False, index=True)
    commit_stats = Column(JSON, nullable=True)
    code_line_stats = Column(JSON, nullable=True)
    create_time = Column(DateTime, nullable=False, index=True)
    stat_time = Column(DateTime, nullable=False, index=True)
    user_repo_mapping = Column(JSON, nullable=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
            name="fk_repo_record_group",
            ondelete="CASCADE",
        ),
    )


class DeliveryType(JsonableEnum):
    group = "group"
    individual = "individual"


class DeliveryItem(Base):
    __tablename__ = "delivery_item"
    id = Column(Integer, primary_key=True)
    item_type = Column(Enum(DeliveryType, name="item_type"), nullable=False, index=True)
    item_file_id = Column(Integer, ForeignKey("file.id"), nullable=True, index=True)
    item_repo_id = Column(
        Integer, ForeignKey("repo_record.id"), nullable=True, index=True
    )
    delivery_id = Column(Integer, ForeignKey("delivery.id"), nullable=False, index=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_file_id"],
            ["file.id"],
            name="fk_repo_record_file",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["item_repo_id"],
            ["repo_record.id"],
            name="fk_repo_record_repo",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["delivery_id"],
            ["delivery.id"],
            name="fk_repo_record_delivery",
            ondelete="CASCADE",
        ),
        UniqueConstraint("item_type", "item_file_id", "item_repo_id"),
    )


class DeliveryStatus(JsonableEnum):
    draft = "draft"
    leader_review = "leader_review"
    leader_rejected = "leader_rejected"
    teacher_review = "teacher_review"
    teacher_rejected = "teacher_rejected"
    teacher_approved = "teacher_approved"


class Delivery(Base):
    __tablename__ = "delivery"
    id = Column(Integer, primary_key=True)
    delivery_items = relationship("DeliveryItem", backref="delivery")
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("group.id"), nullable=False, index=True)
    delivery_user = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
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

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name="fk_delivery_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["group_id"],
            ["group.id"],
            name="fk_delivery_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["delivery_user"],
            ["user.id"],
            name="fk_delivery_user",
            ondelete="CASCADE",
        ),
    )


class AIDocStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class AIDocScoreRecord(Base):
    __tablename__ = "ai_doc_score_record"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("file.id"), nullable=False, index=True)
    status = Column(
        Enum(AIDocStatus, name="score_status"),
        nullable=False,
        index=True,
    )
    create_time = Column(DateTime, nullable=False, index=True)
    score_time = Column(DateTime, nullable=False, index=True)
    doc_evaluation = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=False)


class TeacherScore(Base):
    __tablename__ = "teacher_score"
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, primary_key=True)
    score = Column(Float, nullable=False)
    score_time = Column(DateTime, nullable=False, index=True)
    score_details = Column(JSON, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name="fk_teacher_score_task",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_teacher_score_user",
            ondelete="CASCADE",
        ),
    )


class Log(Base):
    __tablename__ = "log"
    id = Column(Integer, primary_key=True)
    log_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    user_name = Column(String(50), nullable=False, index=True)
    user_employee_id = Column(String(50), nullable=True, index=True)
    user_type = Column(
        Enum(UserType, name="user_type"),
        nullable=False,
        index=True,
    )
    operation_time = Column(DateTime, nullable=False, index=True)
    operation_ip = Column(String(50), nullable=False, index=True)

    # Indexes
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_log_user",
            ondelete="NO ACTION",
        ),
    )


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    update_time = Column(DateTime, nullable=False, index=True)
