from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

import bcrypt
from cryptography.fernet import Fernet
import jwt

from app.config import settings


def _build_sensitive_data_fernet() -> Fernet:
    digest = hashlib.sha256(settings.sensitive_data_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


_sensitive_data_fernet = _build_sensitive_data_fernet()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(account_id: int, login_identifier: str, role: str) -> str:
    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes,
    )
    payload = {
        "sub": str(account_id),
        "login_identifier": login_identifier,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def encrypt_sensitive_value(value: str) -> str:
    return _sensitive_data_fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_sensitive_value(value: str) -> str:
    return _sensitive_data_fernet.decrypt(value.encode("utf-8")).decode("utf-8")


def hash_sensitive_value(value: str) -> str:
    return hmac.new(
        settings.sensitive_data_secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
