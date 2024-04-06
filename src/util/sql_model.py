from model import JsonableEnum


def to_dict(self: any) -> dict:
    """
    Convert a SQLAlchemy model instance to a dictionary.
    :param self: SQLAlchemy model instance
    :return: dictionary
    """
    def convert_value(v):
        if isinstance(v, JsonableEnum):
            return v.to_json()
        return v

    secret_fields = getattr(self, "__secret_fields__", [])

    result = {}

    for column in self.__table__.columns:
        if column.name in secret_fields:
            continue
        value = getattr(self, column.name)
        result[column.name] = convert_value(value)

    return result
