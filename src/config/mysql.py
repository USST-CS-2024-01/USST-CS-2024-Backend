from config.base import Config, InvalidConfigError


class Mysql(Config):
    """
    Mysql configuration
    """

    SECTION = "MYSQL"

    PARAMS = {
        "HOST": "localhost",
        "PORT": 3306,
        "USER": "root",
        "PASSWORD": None,
        "DATABASE": "test",
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
            if field in ["HOST", "USER", "PASSWORD", "DATABASE"] and not isinstance(
                value, str
            ):
                raise InvalidConfigError(field, "value must be a string")
