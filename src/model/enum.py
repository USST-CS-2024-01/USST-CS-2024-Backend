import enum


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
class AnnouncementReceiverType(JsonableEnum):
    all = "all"
    class_ = "class"
    group = "group"
    individual = "individual"
class GroupTaskStatus(JsonableEnum):
    pending = "pending"
    normal = "normal"
    finished = "finished"
class GroupStatus(JsonableEnum):
    pending = "pending"
    normal = "normal"

class FileType(JsonableEnum):
    document = "document"
    other = "other"


class FileOwnerType(JsonableEnum):
    delivery = "delivery"
    group = "group"
    user = "user"

class ClassStatus(JsonableEnum):
    not_started = "not_started"
    grouping = "grouping"
    teaching = "teaching"
    finished = "finished"
class RepoRecordStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class DeliveryType(JsonableEnum):
    group = "group"
    individual = "individual"
class DeliveryStatus(JsonableEnum):
    draft = "draft"
    leader_review = "leader_review"
    leader_rejected = "leader_rejected"
    teacher_review = "teacher_review"
    teacher_rejected = "teacher_rejected"
    teacher_approved = "teacher_approved"

class AIDocStatus(JsonableEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"