import enum
from sanic_ext import openapi


class JsonableEnum(enum.Enum):
    def to_json(self):
        return self.value

    @classmethod
    def from_json(cls, value):
        return cls(value)


@openapi.component
class UserType(JsonableEnum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


@openapi.component
class AccountStatus(JsonableEnum):
    active = "active"
    inactive = "inactive"
    locked = "locked"


@openapi.component
class AnnouncementReceiverType(JsonableEnum):
    all = "all"
    class_ = "class"
    group = "group"
    individual = "individual"


@openapi.component
class GroupTaskStatus(JsonableEnum):
    pending = "pending"
    normal = "normal"
    finished = "finished"


@openapi.component
class GroupStatus(JsonableEnum):
    pending = "pending"
    normal = "normal"


@openapi.component
class FileType(JsonableEnum):
    document = "document"
    other = "other"


@openapi.component
class FileOwnerType(JsonableEnum):
    delivery = "delivery"
    group = "group"
    user = "user"


@openapi.component
class ClassStatus(JsonableEnum):
    not_started = "not_started"
    grouping = "grouping"
    teaching = "teaching"
    finished = "finished"


@openapi.component
class RepoRecordStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


@openapi.component
class DeliveryType(JsonableEnum):
    group = "group"
    individual = "individual"


@openapi.component
class DeliveryStatus(JsonableEnum):
    draft = "draft"
    leader_review = "leader_review"
    leader_rejected = "leader_rejected"
    teacher_review = "teacher_review"
    teacher_rejected = "teacher_rejected"
    teacher_approved = "teacher_approved"


@openapi.component
class AIDocStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
