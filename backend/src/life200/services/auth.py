"""Accounts and passwords. Passwords are hashed with scrypt and a random salt (stdlib only)."""

import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from life200.db.models import UserRow

_N, _R, _P = 2**14, 8, 1
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P)
    return hmac.compare_digest(digest.hex(), digest_hex)  # constant time: no timing leaks


def create_user(session: Session, email: str, password: str, is_admin: bool = False) -> UserRow:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    email = email.strip().casefold()
    user = session.scalar(select(UserRow).where(UserRow.email == email))
    if user is None:
        user = UserRow(email=email, password_hash=hash_password(password), is_admin=is_admin)
        session.add(user)
    else:  # running it again resets the password
        user.password_hash = hash_password(password)
        user.is_admin = user.is_admin or is_admin
    session.flush()
    return user


def authenticate(session: Session, email: str, password: str) -> UserRow | None:
    user = session.scalar(select(UserRow).where(UserRow.email == email.strip().casefold()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user
