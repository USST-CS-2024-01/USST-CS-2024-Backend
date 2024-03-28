from config.base import Config, InvalidConfigError


class Redis(Config):
    """
    Redis configuration
    """

    SECTION = "REDIS"

    PARAMS = {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        "PASSWORD": None,
    }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        for field, value in self.__dict__.items():
            if field in ["PORT", "DB"] and not isinstance(value, int):
                raise InvalidConfigError(field, "value must be an integer")
            if field in ["HOST", "PASSWORD"] and not isinstance(value, str):
                raise InvalidConfigError(field, "value must be a string")
