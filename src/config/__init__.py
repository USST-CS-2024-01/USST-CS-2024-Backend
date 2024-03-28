import yaml
from sanic.config import Config as SanicConfig

CONFIG_FILE = "config.yaml"
INJECTION_MODULES = ["goflet", "mysql", "redis"]


def load_config(config_file: str = CONFIG_FILE):
    """
    Load configuration from a YAML file
    :param config_file: configuration file
    :return: dictionary
    """
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


def inject_config(conf: SanicConfig, config_file: str = CONFIG_FILE):
    """
    Inject configuration into a Sanic application
    :param conf: Sanic application
    :param config_file: configuration file
    :return: None
    """
    config_data = load_config(config_file)

    for module in INJECTION_MODULES:
        module = __import__(f"config.{module}", fromlist=[module])
        module = getattr(module, module.__name__.split(".")[-1].capitalize())

        # Instantiate the module and load the configuration
        config = module()
        config.load(config_data)

        # Update the Sanic configuration
        conf.update(config.dict())
