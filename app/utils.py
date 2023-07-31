# -*- coding: utf-8 -*-
import base64
import hashlib
import secrets

from pydantic import BaseModel

from app import config


class Status(BaseModel):
    message: str
    success: bool


def password_hash(password: str, salt: str = None, iterations: int = None) -> str:
    """Hash a password.

    Args:
        password (str): The password to hash.

    Returns:
        str: The hashed password.
    """
    if not salt:
        salt = secrets.token_hex(16)
    if not iterations:
        iterations = config.PASSWORD_HASH_NUMBER_OF_ITERATIONS
    assert isinstance(password, str)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    b64_hash = base64.b64encode(pw_hash).decode("ascii").strip()
    return "{}${}${}${}".format(
        config.PASSWORD_HASH_ALGORITHM,
        iterations,
        salt,
        b64_hash,
    )


def password_verify(password: str, hashed: str) -> bool:
    """Verify a password against a hash.

    Args:
        password (str): The password to verify.
        hashed (str): The hashed password to verify against.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    if (hashed or "").count("$") != 3:
        return False
    algorithm, iterations, salt, _ = hashed.split("$", 3)
    iterations = int(iterations)
    assert algorithm == config.PASSWORD_HASH_ALGORITHM
    compare_hash = password_hash(password, salt, iterations)
    return secrets.compare_digest(hashed, compare_hash)
