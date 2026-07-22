from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from fastapi import HTTPException, Request, status
from app.database import connection

_ITERATIONS = 310_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def ensure_admin_password() -> None:
    default_password = os.getenv("DASHBOARD_MATRIX_ADMIN_PASSWORD", "admin")
    with connection() as conn:
        row = conn.execute("SELECT value FROM station_settings WHERE key='admin_password_hash'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO station_settings(key,value) VALUES('admin_password_hash',?)",
                (hash_password(default_password),),
            )


def authenticate(password: str) -> bool:
    with connection() as conn:
        row = conn.execute("SELECT value FROM station_settings WHERE key='admin_password_hash'").fetchone()
    return bool(row and verify_password(password, row[0]))


def change_password(new_password: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO station_settings(key,value) VALUES('admin_password_hash',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (hash_password(new_password),),
        )


def require_admin(request: Request) -> None:
    if not request.session.get("admin_authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required")
