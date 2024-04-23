from config.base import Config, InvalidConfigError


class Kafka(Config):
    """
    Mysql configuration
    """

    SECTION = "KAFKA"

    PARAMS = {
        "HOST": "localhost",
        "PORT": 9092,
    }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        for field, value in self.__dict__.items():
            if field in ["PORT"] and not isinstance(value, int):
                raise InvalidConfigError(field, "value must be an integer")
            if field in ["HOST"] and not isinstance(value, str):
                raise InvalidConfigError(field, "value must be a string")
