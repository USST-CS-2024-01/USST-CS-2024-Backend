from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sanic_ext import openapi

from .enum import (
    UserType,
    AccountStatus,
    AnnouncementReceiverType,
    GroupStatus,
    FileType,
    FileOwnerType,
    ClassStatus,
    RepoRecordStatus,
    DeliveryType,
    DeliveryStatus,
    AIDocStatus,
    GroupTaskStatus,
    GroupMemberRoleStatus,
)


def _datetime_to_timestamp(v: datetime) -> int:
    try:
        return int(v.timestamp())
    except Exception as e:
        return 0


class BaseJsonAbleModel(BaseModel):
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: _datetime_to_timestamp,
            UserType: lambda v: v.value,
            AccountStatus: lambda v: v.value,
            AnnouncementReceiverType: lambda v: v.value,
            GroupStatus: lambda v: v.value,
            FileType: lambda v: v.value,
            FileOwnerType: lambda v: v.value,
            ClassStatus: lambda v: v.value,
            RepoRecordStatus: lambda v: v.value,
            DeliveryType: lambda v: v.value,
            DeliveryStatus: lambda v: v.value,
            AIDocStatus: lambda v: v.value,
            GroupTaskStatus: lambda v: v.value,
        }

    def dict(self, **kwargs):
        return super().dict(**kwargs)

    def json(self, **kwargs):
        return super().json(**kwargs)


@openapi.component()
class UserSchema(BaseJsonAbleModel):
    id: int
    username: str
    # password_hash: str; Hide for this is a secret field
    email: Optional[str] = None
    user_type: UserType
    account_status: AccountStatus
    employee_id: Optional[str] = None
    name: str


@openapi.component()
class FileSchema(BaseJsonAbleModel):
    id: int
    name: str
    file_type: FileType
    file_size: int
    owner_type: FileOwnerType
    owner_delivery_id: Optional[int] = None
    owner_group_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    owner_clazz_id: Optional[int] = None
    create_date: datetime
    modify_date: datetime
    tags: Optional[List[str]] = None


@openapi.component()
class AnnouncementSchema(BaseJsonAbleModel):
    id: int
    title: str
    content: str
    attachment: List["FileSchema"]
    publisher: int
    receiver_type: AnnouncementReceiverType
    receiver_class_id: Optional[int] = None
    receiver_group_id: Optional[int] = None
    receiver_user_id: Optional[int] = None
    read_users: List[UserSchema]
    publish_time: datetime


@openapi.component()
class AnnouncementReadSchema(BaseJsonAbleModel):
    announcement_id: int
    user_id: int
    read_time: datetime


@openapi.component()
class AnnouncementAttachmentSchema(BaseJsonAbleModel):
    announcement_id: int
    file_id: int


@openapi.component()
class GroupRoleSchema(BaseJsonAbleModel):
    id: int
    class_id: int
    role_name: str
    role_description: str
    is_manager: bool


@openapi.component()
class GroupTaskSchema(BaseJsonAbleModel):
    id: int
    group_id: int
    name: str
    details: str
    status: GroupTaskStatus
    related_files: List["FileSchema"]
    publisher: int
    assignees: List[GroupRoleSchema]
    publish_time: datetime
    deadline: datetime
    update_time: datetime


@openapi.component()
class GroupTaskAttachmentSchema(BaseJsonAbleModel):
    task_id: int
    file_id: int


@openapi.component()
class GroupTaskAssigneeSchema(BaseJsonAbleModel):
    task_id: int
    role_id: int


@openapi.component()
class GroupMeetingSchema(BaseJsonAbleModel):
    id: int
    group_id: int
    name: str
    start_time: datetime
    end_time: datetime
    participants: List[UserSchema]
    meeting_type: str
    meeting_link: Optional[str] = None
    related_files: List["FileSchema"]


@openapi.component()
class GroupMeetingParticipantSchema(BaseJsonAbleModel):
    meeting_id: int
    user_id: int


@openapi.component()
class GroupMeetingAttachmentSchema(BaseJsonAbleModel):
    meeting_id: int
    file_id: int


@openapi.component()
class GroupMemberRoleSchema(BaseJsonAbleModel):
    class_member_id: int
    role_id: int


@openapi.component()
class ClassMemberSchema(BaseJsonAbleModel):
    id: int
    class_id: int
    user_id: int
    group_id: Optional[int] = None
    roles: Optional[List[GroupRoleSchema]] = None
    repo_usernames: Optional[list] = None
    is_teacher: bool
    status: Optional[GroupMemberRoleStatus] = None

    user: UserSchema


@openapi.component()
class GroupSchema(BaseJsonAbleModel):
    id: int
    class_id: int
    name: str
    status: GroupStatus
    current_task_id: Optional[int] = None
    members: List["ClassMemberSchema"]


@openapi.component()
class TaskSchema(BaseJsonAbleModel):
    id: int
    class_id: Optional[int] = None
    name: str
    content: str
    specified_role: Optional[int] = None
    attached_files: List[FileSchema]
    publish_time: datetime
    deadline: datetime
    grade_percentage: float
    next_task_id: Optional[int] = None


@openapi.component()
class ClassSchema(BaseJsonAbleModel):
    id: int
    name: str
    description: Optional[str] = None
    first_task_id: Optional[int] = None
    task_list: Optional[List["TaskSchema"]] = None
    status: ClassStatus


@openapi.component()
class TaskAttachmentSchema(BaseJsonAbleModel):
    task_id: int
    file_id: int


@openapi.component()
class RepoRecordSchema(BaseJsonAbleModel):
    id: int
    status: RepoRecordStatus
    repo_url: str
    group_id: int
    commit_stats: Optional[dict] = None
    code_line_stats: Optional[dict] = None
    create_time: datetime
    stat_time: datetime
    user_repo_mapping: Optional[dict] = None


@openapi.component()
class DeliveryItemSchema(BaseJsonAbleModel):
    id: int
    item_type: DeliveryType
    item_file_id: Optional[int] = None
    item_repo_id: Optional[int] = None
    delivery_id: int


@openapi.component()
class DeliverySchema(BaseJsonAbleModel):
    id: int
    delivery_items: List[DeliveryItemSchema]
    task_id: int
    group_id: int
    delivery_user: int
    delivery_time: datetime
    delivery_status: DeliveryStatus
    delivery_comments: Optional[str] = None
    comment_time: Optional[datetime] = None
    task_grade_percentage: float


@openapi.component()
class AIDocScoreRecordSchema(BaseJsonAbleModel):
    id: int
    file_id: int
    status: AIDocStatus
    create_time: datetime
    score_time: datetime
    doc_evaluation: Optional[dict] = None
    overall_score: float


@openapi.component()
class TeacherScoreSchema(BaseJsonAbleModel):
    task_id: int
    user_id: int
    score: float
    score_time: datetime
    score_details: Optional[dict] = None


@openapi.component()
class LogSchema(BaseJsonAbleModel):
    id: int
    log_type: str
    content: str
    user_id: int
    user_name: str
    user_employee_id: Optional[str] = None
    user_type: UserType
    operation_time: datetime
    operation_ip: str


@openapi.component()
class ConfigSchema(BaseJsonAbleModel):
    id: int
    key: str
    value: str
    update_time: datetime


@openapi.component()
class TaskGroupMemberScoreSchema(BaseJsonAbleModel):
    task_id: int
    group_id: int
    group_manager_score: Optional[dict] = None
    group_member_scores: Optional[str] = None
