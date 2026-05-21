import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def load_private_key(pem: str):
    pem_bytes = pem.encode("utf-8") if isinstance(pem, str) else pem
    return serialization.load_pem_private_key(pem_bytes, password=None, backend=default_backend())


def load_public_key(pem: str):
    pem_bytes = pem.encode("utf-8") if isinstance(pem, str) else pem
    return serialization.load_pem_public_key(pem_bytes, backend=default_backend())


def load_private_key_from_file(path: str):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())


def load_public_key_from_file(path: str):
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read(), backend=default_backend())
