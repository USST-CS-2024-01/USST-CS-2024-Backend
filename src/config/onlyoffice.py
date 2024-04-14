from config.base import Config, InvalidConfigError


class Onlyoffice(Config):
    """
    OnlyOffice configuration
    """

    SECTION = "ONLYOFFICE"

    PARAMS = {
        "ENDPOINT": "http://localhost:18000",
        "SECRET": "secret",
    }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        for field, value in self.__dict__.items():
            if field in ["ENDPOINT", "SECRET"] and not isinstance(value, str):
                raise InvalidConfigError(field, "value must be a string")
