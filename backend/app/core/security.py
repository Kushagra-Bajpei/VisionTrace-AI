"""
VisionTrace AI – Security Core: Password Hashing, JWT Tokens, and Revocation.
Enforces bcrypt hashing, explicit HS256 JWT validation, and token revocation.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit import RevokedToken

logger = logging.getLogger(__name__)
settings = get_settings()

ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_MEDIA_TOKEN_EXPIRE_SECONDS = 120


# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.warning("Bcrypt verification failed: %s", e)
        return False


# ── JWT Token Generation & Validation ────────────────────────────────────────

def create_access_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a cryptographically signed general-purpose JWT access token.
    Contains explicit jti, token_type='access', and expiration.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES))
    jti = str(uuid.uuid4())

    payload = {
        "jti": jti,
        "token_type": "access",
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


def create_media_token(
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    expires_in_seconds: int = DEFAULT_MEDIA_TOKEN_EXPIRE_SECONDS,
) -> str:
    """
    Creates a tightly scoped, short-lived media token bound to a specific resource.
    token_type='media'. Cannot be used for general API access.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=expires_in_seconds)
    jti = str(uuid.uuid4())

    payload = {
        "jti": jti,
        "token_type": "media",
        "sub": str(user_id),
        "resource_type": resource_type.lower().strip(),
        "resource_id": str(resource_id).strip(),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies a JWT token.
    Enforces algorithm='HS256' to prevent algorithm confusion attacks.
    """
    try:
        payload = jwt.decode(
            token,
            settings.app_secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "jti", "sub", "token_type"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")


# ── Revocation / Blacklist ───────────────────────────────────────────────────

def is_token_revoked(db: Session, jti: str) -> bool:
    """Checks whether the token identifier (jti) has been persistently revoked."""
    if not jti:
        return True
    revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    return revoked is not None


def revoke_token(
    db: Session,
    jti: str,
    user_id: uuid.UUID,
    expires_at_timestamp: int,
) -> None:
    """Records a token in the revocation table until its natural expiry."""
    expires_dt = datetime.fromtimestamp(expires_at_timestamp, tz=timezone.utc)
    revoked = RevokedToken(
        id=uuid.uuid4(),
        jti=jti,
        user_id=user_id,
        expires_at=expires_dt,
    )
    db.add(revoked)
    db.commit()


def cleanup_expired_revocations(db: Session) -> int:
    """Cleans up expired revoked token records."""
    now = datetime.now(timezone.utc)
    count = db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete()
    db.commit()
    return count
