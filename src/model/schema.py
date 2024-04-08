from datetime import datetime
from typing import List, Optional
from sanic_ext import openapi
from pydantic import BaseModel

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
)


class BaseJsonAbleModel(BaseModel):
    class Config:
        orm_mode = True
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.timestamp(),
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


@openapi.component
class UserSchema(BaseJsonAbleModel):
    id: int
    username: str
    # password_hash: str; Hide for this is a secret field
    email: Optional[str] = None
    user_type: UserType
    account_status: AccountStatus
    employee_id: Optional[str] = None
    name: str


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


class AnnouncementReadSchema(BaseJsonAbleModel):
    announcement_id: int
    user_id: int
    read_time: datetime


class AnnouncementAttachmentSchema(BaseJsonAbleModel):
    announcement_id: int
    file_id: int


class GroupRoleSchema(BaseJsonAbleModel):
    id: int
    class_id: int
    role_name: str
    role_description: str


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


class GroupTaskAttachmentSchema(BaseJsonAbleModel):
    task_id: int
    file_id: int


class GroupTaskAssigneeSchema(BaseJsonAbleModel):
    task_id: int
    role_id: int


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


class GroupMeetingParticipantSchema(BaseJsonAbleModel):
    meeting_id: int
    user_id: int


class GroupMeetingAttachmentSchema(BaseJsonAbleModel):
    meeting_id: int
    file_id: int


class GroupMemberSchema(BaseJsonAbleModel):
    id: int
    user_id: int
    group_id: int
    roles: List[GroupRoleSchema]
    repo_usernames: dict


class GroupMemberRoleSchema(BaseJsonAbleModel):
    group_member_id: int
    role_id: int


class GroupSchema(BaseJsonAbleModel):
    id: int
    class_id: int
    name: str
    status: GroupStatus
    current_task_id: Optional[int] = None


class FileSchema(BaseJsonAbleModel):
    id: int
    name: str
    file_type: FileType
    file_size: int
    owner_type: FileOwnerType
    owner_delivery_id: Optional[int] = None
    owner_group_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    create_date: datetime
    modify_date: datetime
    tags: Optional[dict] = None


class ClassSchema(BaseJsonAbleModel):
    id: int
    name: str
    description: Optional[str] = None
    first_task_id: Optional[int] = None
    task_list: List["TaskSchema"]
    status: ClassStatus


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


class TaskAttachmentSchema(BaseJsonAbleModel):
    task_id: int
    file_id: int


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


class DeliveryItemSchema(BaseJsonAbleModel):
    id: int
    item_type: DeliveryType
    item_file_id: Optional[int] = None
    item_repo_id: Optional[int] = None
    delivery_id: int


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


class AIDocScoreRecordSchema(BaseJsonAbleModel):
    id: int
    file_id: int
    status: AIDocStatus
    create_time: datetime
    score_time: datetime
    doc_evaluation: Optional[dict] = None
    overall_score: float


class TeacherScoreSchema(BaseJsonAbleModel):
    task_id: int
    user_id: int
    score: float
    score_time: datetime
    score_details: Optional[dict] = None


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


class ConfigSchema(BaseJsonAbleModel):
    id: int
    key: str
    value: str
    update_time: datetime
