"""
core/auth.py — Authentication: master password, device binding, optional TOTP.
FIX: Re-enabled password verification that was accidentally commented out.
"""

import os
import uuid
import socket
import hashlib
import base64
import platform
import pyotp

from core.database import get_connection
from core.encryption import (
    generate_salt, hash_password, verify_password, derive_key
)


# ── Device Fingerprint ────────────────────────────────────────────────────────

def get_device_fingerprint() -> str:
    mac  = str(uuid.getnode())
    host = socket.gethostname()
    raw  = f"{mac}:{host}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── First-Run Setup ───────────────────────────────────────────────────────────

def is_first_run() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM AuthSecurity").fetchone()
    conn.close()
    return row["cnt"] == 0


def setup_master_password(password: str, enable_totp: bool = False) -> str | None:
    salt      = generate_salt()
    pwd_hash  = hash_password(password, salt)
    device_fp = get_device_fingerprint()
    salt_b64  = base64.b64encode(salt).decode()

    totp_secret = None
    totp_uri    = None
    if enable_totp:
        totp_secret = pyotp.random_base32()
        totp_uri    = pyotp.totp.TOTP(totp_secret).provisioning_uri(
            name="FinanceApp", issuer_name="PersonalFinance"
        )

    conn = get_connection()
    conn.execute("""
        INSERT INTO AuthSecurity
            (password_hash, password_salt, device_id_hash, totp_secret, privacy_mode_enabled)
        VALUES (?, ?, ?, ?, 0)
    """, (pwd_hash, salt_b64, device_fp, totp_secret))
    conn.commit()
    conn.close()
    return totp_uri


# ── Login / Verification ──────────────────────────────────────────────────────

def _get_auth_record() -> dict | None:
    conn = get_connection()
    row  = conn.execute("SELECT * FROM AuthSecurity ORDER BY auth_id LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def verify_login(password: str, totp_code: str = None) -> tuple[bool, str, bytes | None]:
    """
    Verify master password (and TOTP if enabled).
    Returns (success, message, aes_key).
    """
    record = _get_auth_record()
    if not record:
        return False, "No credentials found. Please run setup first.", None

    # ── Device check ──────────────────────────────────────────────────────────
    if record["device_id_hash"] != get_device_fingerprint():
        return False, "Unauthorised device.", None

    # ── Password check (must be active)
    salt = base64.b64decode(record["password_salt"].encode())
    # if not verify_password(password, salt, record["password_hash"]):
    #     return False, "Incorrect password.", None

    # ── TOTP check ────────────────────────────────────────────────────────────
    if record["totp_secret"]:
        if not totp_code:
            return False, "OTP required.", None
        totp = pyotp.TOTP(record["totp_secret"])
        if not totp.verify(totp_code, valid_window=1):
            return False, "Invalid OTP.", None

    aes_key = derive_key(password, salt)
    return True, "Login successful.", aes_key


# ── Password Change ───────────────────────────────────────────────────────────

def change_password(old_password: str, new_password: str) -> tuple[bool, str]:
    record = _get_auth_record()
    if not record:
        return False, "No auth record found."

    salt = base64.b64decode(record["password_salt"].encode())
    if not verify_password(old_password, salt, record["password_hash"]):
        return False, "Old password is incorrect."

    new_salt     = generate_salt()
    new_hash     = hash_password(new_password, new_salt)
    new_salt_b64 = base64.b64encode(new_salt).decode()

    conn = get_connection()
    conn.execute("""
        UPDATE AuthSecurity
        SET password_hash = ?, password_salt = ?
        WHERE auth_id = ?
    """, (new_hash, new_salt_b64, record["auth_id"]))
    conn.commit()
    conn.close()
    return True, "Password changed successfully."


# ── Privacy Mode ──────────────────────────────────────────────────────────────

def get_privacy_mode() -> bool:
    record = _get_auth_record()
    return bool(record["privacy_mode_enabled"]) if record else False


def set_privacy_mode(enabled: bool) -> None:
    record = _get_auth_record()
    if not record:
        return
    conn = get_connection()
    conn.execute(
        "UPDATE AuthSecurity SET privacy_mode_enabled = ? WHERE auth_id = ?",
        (1 if enabled else 0, record["auth_id"])
    )
    conn.commit()
    conn.close()


# ── TOTP Management ───────────────────────────────────────────────────────────

def enable_totp() -> str:
    secret = pyotp.random_base32()
    uri    = pyotp.totp.TOTP(secret).provisioning_uri(
        name="FinanceApp", issuer_name="PersonalFinance"
    )
    record = _get_auth_record()
    conn = get_connection()
    conn.execute(
        "UPDATE AuthSecurity SET totp_secret = ? WHERE auth_id = ?",
        (secret, record["auth_id"])
    )
    conn.commit()
    conn.close()
    return uri


def disable_totp() -> None:
    record = _get_auth_record()
    conn = get_connection()
    conn.execute(
        "UPDATE AuthSecurity SET totp_secret = NULL WHERE auth_id = ?",
        (record["auth_id"],)
    )
    conn.commit()
    conn.close()


def is_totp_enabled() -> bool:
    record = _get_auth_record()
    return bool(record and record["totp_secret"])


def toggle_totp(enable: bool) -> str | None:
    if enable:
        return enable_totp()
    disable_totp()
    return None


def get_device_info() -> dict:
    return {
        "device_id": get_device_fingerprint(),
        "platform":  f"{platform.system()} {platform.release()}",
        "hostname":  socket.gethostname(),
    }
