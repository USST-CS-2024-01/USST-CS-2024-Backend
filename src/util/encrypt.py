import os
import traceback
from binascii import crc32

import bcrypt
from Crypto.Cipher import AES


def generate_key_iv() -> tuple:
    """
    Generate a key and iv for AES encryption
    :return: (key, iv)
    """
    key = os.urandom(16)
    iv = os.urandom(16)
    return key, iv


def decrypt_aes(key: bytes, iv: bytes, data: bytes) -> bytes:
    """
    Decrypt data using AES, the data should be able to be decoded to utf-8

    :param key: Key
    :param iv: IV
    :param data: Data to decrypt
    :return: Decrypted data
    """
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(data)

    try:
        decrypted = decrypted.decode("utf-8").strip().encode("utf-8")
    except Exception:
        raise ValueError("Invalid password")

    return decrypted


def bcrypt_compare(password: str, hashed: str) -> bool:
    """
    Compare a password with a hashed password
    :param password: Password
    :param hashed: Hashed password
    :return: True if the password matches the hashed password, False otherwise
    """
    return bcrypt.checkpw(password.encode(), hashed.encode())
