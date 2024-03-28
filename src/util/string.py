def underline_to_camelcase(underline: str, initial_upper: bool = True) -> str:
    """
    Convert underline string to camelcase string.

    Example:

    - underline_to_camelcase('hello_world') -> 'HelloWorld'
    - underline_to_camelcase('hello_world_hello') -> 'HelloWorldHello'
    - underline_to_camelcase('hello_world_hello', False) -> 'helloWorldHello'

    :param underline: Underline string
    :param initial_upper: Initial letter is uppercase
    :return: camelcase string
    """
    camelcase = "".join(word.capitalize() for word in underline.split("_"))
    if not initial_upper:
        camelcase = camelcase[0].lower() + camelcase[1:]
    return camelcase


def camelcase_to_underline(camelcase: str, capitalize: bool = False) -> str:
    """
    Convert camelcase string to underline string.

    Example:

    - camelcase_to_underline('HelloWorld') -> 'hello_world'
    - camelcase_to_underline('HelloWorldHello') -> 'hello_world_hello'
    - camelcase_to_underline('helloWorldHello') -> 'hello_world_hello'
    - camelcase_to_underline('helloWorldHello', True) -> 'HELLO_WORLD_HELLO'

    :param camelcase: Camelcase string
    :param capitalize: Capitalize the underline string
    :return: underline string
    """
    underline = "".join(
        f"_{c.lower()}" if c.isupper() else c for c in camelcase
    ).lstrip("_")
    if capitalize:
        underline = underline.upper()
    return underline


