"""Encryption for things we must be able to read back later, like project secrets.

Uses Fernet from `cryptography` (AES with a signature, so a changed value is refused, not misread).
The key is SECRETS_KEY in dakdot/.env. Make one with:

    uv run manage.py secrets_key

To change keys, put the new key first and keep the old one after a comma (SECRETS_KEY=new,old): the first key
encrypts, all of them decrypt. Then run `uv run manage.py rotate_secrets` and drop the old key.

Lose the key and the saved secrets cannot be read again: keep a copy somewhere safe, not only on the server.
"""
from functools import cache

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@cache
def _fernet():
    keys = [key.strip() for key in settings.SECRETS_KEY.split(",") if key.strip()]
    if not keys:
        raise ImproperlyConfigured("Set SECRETS_KEY in dakdot/.env. `uv run manage.py secrets_key` makes one.")
    return MultiFernet([Fernet(key) for key in keys])


def new_key():
    return Fernet.generate_key().decode()


def encrypt(text):
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token):
    return _fernet().decrypt(token.encode()).decode()


def reencrypt(token):
    """The same value encrypted with the first (newest) key."""
    return _fernet().rotate(token.encode()).decode()
