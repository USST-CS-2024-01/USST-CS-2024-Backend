from config.base import Config, InvalidConfigError

_JWT_ALGORITHMS = [
    "HS256",
    "HS384",
    "HS512",
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
    "PS256",
    "PS384",
    "PS512",
]


class Api(Config):
    """
    Api configuration
    """

    SECTION = "API"

    PARAMS = {
        "BASE_URL": ...,
    }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        for field, value in self.__dict__.items():
            if field == "BASE_URL" and not isinstance(value, str):
                raise InvalidConfigError(field, "value must be a string")
