from typing import Optional
from util.string import underline_to_camelcase


class Config:
    """
    Base configuration class
    """

    SECTION: str
    PARAMS: dict

    def __repr__(self):
        attrs = [f"{k}={v}" for k, v in self.__dict__.items()]
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def __str__(self):
        return self.__repr__()

    def load(self, dict_data: dict):
        """
        Load configuration from a dictionary
        :param dict_data: dictionary
        :return: dictionary of configuration, with the same keys as PARAMS
        """
        section_data = (
            dict_data.get(self.SECTION)
            or dict_data.get(underline_to_camelcase(self.SECTION, False))
            or {}
        )
        for field, default_value in self.PARAMS.items():
            value = section_data.get(field) or section_data.get(
                underline_to_camelcase(field, False)
            )
            if value is None and default_value is not None:
                value = default_value
            if value is None:
                raise InvalidConfigError(field, "value is required")
            setattr(self, field, value)
        self.check()

    def dict(self):
        """
        Return a dictionary representation of the configuration
        :return: dictionary
        """
        return {
            self.SECTION + "_" + k: v
            for k, v in self.__dict__.items()
            if k in self.PARAMS
        }

    def check(self) -> None:
        """
        Check if the configuration is valid
        Raise an exception if the configuration is invalid
        :return: None
        """
        raise NotImplementedError("check method is not implemented")


class InvalidConfigError(Exception):
    """
    Invalid configuration error
    """

    def __init__(self, field, message):
        self.field = underline_to_camelcase(field, False)
        self.message = message

        super().__init__(f"Invalid configuration for {self.field}: {self.message}")
