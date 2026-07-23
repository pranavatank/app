"""
core/encryption.py — AES-256 encryption/decryption and key management
Uses PBKDF2-HMAC-SHA256 for key derivation from master password.
"""

import os
import base64
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from config import PBKDF2_ITERATIONS, SALT_SIZE, AES_KEY_SIZE


# ── Key Derivation ────────────────────────────────────────────────────────────

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from the master password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def generate_salt() -> bytes:
    """Generate a cryptographically secure random salt."""
    return os.urandom(SALT_SIZE)


# ── AES-GCM Encrypt / Decrypt ─────────────────────────────────────────────────

def encrypt_data(data: bytes, key: bytes) -> bytes:
    """
    Encrypt data with AES-256-GCM.
    Returns: nonce (12 bytes) + ciphertext+tag
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt_data(encrypted: bytes, key: bytes) -> bytes:
    """
    Decrypt AES-256-GCM data.
    Input: nonce (12 bytes) + ciphertext+tag
    """
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ── Field-Level Encryption (for sensitive DB fields) ─────────────────────────

def encrypt_field(value: str, key: bytes) -> str:
    """Encrypt a string field; returns base64-encoded string for DB storage."""
    if value is None:
        return None
    encrypted = encrypt_data(value.encode("utf-8"), key)
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_field(value: str, key: bytes) -> str:
    """Decrypt a base64-encoded encrypted field from DB."""
    if value is None:
        return None
    encrypted = base64.b64decode(value.encode("ascii"))
    return decrypt_data(encrypted, key).decode("utf-8")


# ── File-Level Encryption (for DB file and backups) ──────────────────────────

def encrypt_file(input_path: str, output_path: str, key: bytes) -> None:
    """Encrypt a file and write to output_path."""
    with open(input_path, "rb") as f:
        data = f.read()
    encrypted = encrypt_data(data, key)
    with open(output_path, "wb") as f:
        f.write(encrypted)


def decrypt_file(input_path: str, output_path: str, key: bytes) -> None:
    """Decrypt an encrypted file and write to output_path."""
    with open(input_path, "rb") as f:
        encrypted = f.read()
    data = decrypt_data(encrypted, key)
    with open(output_path, "wb") as f:
        f.write(data)


# ── Password Hashing (for stored verification) ───────────────────────────────

def hash_password(password: str, salt: bytes) -> str:
    """Hash the master password with salt using SHA-256. Returns hex string."""
    h = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )
    return h.hex()


def verify_password(password: str, salt: bytes, stored_hash: str) -> bool:
    """Verify a password against its stored hash (constant-time comparison)."""
    return hmac.compare_digest(hash_password(password, salt), stored_hash)
