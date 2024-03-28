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


class Goflet(Config):
    """
    Goflet configuration
    """

    SECTION = "GOFLET"

    PARAMS = {
        "BASE_URL": ...,
        "JWT_ALGORITHM": ...,
        "JWT_SECRET": None,
        "JWT_PRIVATE_KEY": None,
        "JWT_ISSUER": "goflet",
        "JWT_EXPIRATION": 3600,
    }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        for field, value in self.__dict__.items():
            if field == "JWT_ALGORITHM" and value not in _JWT_ALGORITHMS:
                raise InvalidConfigError(field, "unsupported algorithm")
            if field == "JWT_EXPIRATION" and not isinstance(value, int):
                raise InvalidConfigError(field, "value must be an integer")
            if field == "BASE_URL" and not isinstance(value, str):
                raise InvalidConfigError(field, "value must be a string")
