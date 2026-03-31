"""
engines/ais_tis_decryptor.py — Decrypt password-protected AIS/TIS JSON files
"""

import base64
import binascii
import gzip
import hashlib
import json
import re
import zlib
from typing import Any, Optional, Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


_B64_RE = re.compile(r"^[A-Za-z0-9+/=_-]+$")
_HEX64_B64_RE = re.compile(r"^[0-9a-fA-F]{64}[A-Za-z0-9+/=_-]+$")


def _normalize_password(password: str) -> str:
    # Income Tax portal passwords are case-sensitive in practice, but PAN is typically uppercase.
    # We keep user input as-is except trimming whitespace, and we uppercase the PAN-like prefix
    # (common user error is entering PAN in lowercase).
    pw = (password or "").strip()
    if len(pw) >= 10 and re.fullmatch(r"[A-Za-z]{5}[0-9]{4}[A-Za-z]", pw[:10]):
        pw = pw[:10].upper() + pw[10:]
    return pw


def _b64decode_relaxed(data: str) -> bytes:
    data = data.strip()
    # Some portal outputs use URL-safe base64 without padding.
    data = data.replace('-', '+').replace('_', '/')
    pad_len = (-len(data)) % 4
    if pad_len:
        data += "=" * pad_len
    return base64.b64decode(data)


def _maybe_decode_hex(data: str) -> Optional[bytes]:
    data = data.strip()
    if not data:
        return None
    if len(data) % 2 != 0:
        return None
    if not re.fullmatch(r"[0-9a-fA-F]+", data):
        return None
    try:
        return binascii.unhexlify(data)
    except binascii.Error:
        return None


def _is_probably_base64(s: str) -> bool:
    if not s or len(s) < 16:
        return False
    if not _B64_RE.fullmatch(s.strip()):
        return False
    # Heuristic: base64 strings are typically multiple of 4 once padded.
    return True


def _evp_bytes_to_key(password_bytes: bytes, salt: bytes, key_len: int, iv_len: int) -> Tuple[bytes, bytes]:
    """OpenSSL EVP_BytesToKey compatible key derivation (MD5, 1 iteration).

    CryptoJS (passphrase mode) and OpenSSL salted format both commonly use this.
    """
    derived = b""
    block = b""
    while len(derived) < (key_len + iv_len):
        block = hashlib.md5(block + password_bytes + salt).digest()
        derived += block
    key = derived[:key_len]
    iv = derived[key_len:key_len + iv_len]
    return key, iv


def _pkcs7_unpad(padded_plaintext: bytes) -> bytes:
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded_plaintext) + unpadder.finalize()


def _aes_cbc_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return _pkcs7_unpad(padded_plaintext)


def _aes_cbc_decrypt_raw(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def _aes_stream_decrypt(ciphertext: bytes, key: bytes, iv: bytes, mode: str) -> bytes:
    if mode == "CTR":
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
    elif mode == "CFB":
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    else:
        raise ValueError(f"Unsupported stream mode: {mode}")
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def _decrypt_openssl_salted(encrypted_bytes: bytes, password: str) -> bytes:
    if not encrypted_bytes.startswith(b"Salted__") or len(encrypted_bytes) < 16:
        raise ValueError("Not OpenSSL salted format")
    salt = encrypted_bytes[8:16]
    ciphertext = encrypted_bytes[16:]
    key, iv = _evp_bytes_to_key(_normalize_password(password).encode("utf-8"), salt, 32, 16)
    return _aes_cbc_decrypt(ciphertext, key, iv)


def _decrypt_cryptojs_json(envelope: dict, password: str) -> bytes:
    """Decrypt CryptoJS AES JSON format: {ct: base64, iv: hex, s: hex}."""
    ct = envelope.get("ct")
    iv_hex = envelope.get("iv")
    salt_hex = envelope.get("s")
    if not (isinstance(ct, str) and isinstance(iv_hex, str) and isinstance(salt_hex, str)):
        raise ValueError("Not a CryptoJS AES JSON envelope")

    salt = _maybe_decode_hex(salt_hex)
    iv = _maybe_decode_hex(iv_hex)
    if salt is None or iv is None:
        raise ValueError("Invalid CryptoJS iv/salt encoding")

    ciphertext = _b64decode_relaxed(ct)
    key, _iv = _evp_bytes_to_key(_normalize_password(password).encode("utf-8"), salt, 32, 16)
    # CryptoJS envelope already supplies iv; use it.
    return _aes_cbc_decrypt(ciphertext, key, iv)


def _decrypt_pbkdf2_envelope(envelope: dict, password: str) -> bytes:
    """Decrypt a common PBKDF2 envelope: ciphertext + iv + salt + iterations.

    This is a best-effort implementation for portal-style exports that store crypto params.
    """
    ciphertext_s = envelope.get("ciphertext") or envelope.get("ct") or envelope.get("data")
    iv_s = envelope.get("iv")
    salt_s = envelope.get("salt") or envelope.get("s")
    if not (isinstance(ciphertext_s, str) and isinstance(iv_s, str) and isinstance(salt_s, str)):
        raise ValueError("Not a PBKDF2 envelope")

    iterations = envelope.get("iterations") or envelope.get("iter") or envelope.get("it") or 10000
    try:
        iterations = int(iterations)
    except Exception:
        iterations = 10000

    key_size = envelope.get("keySize") or envelope.get("ks") or 256
    try:
        key_len = int(key_size) // 8
    except Exception:
        key_len = 32
    if key_len not in (16, 24, 32):
        key_len = 32

    # Decode iv/salt as hex if possible, else base64.
    iv = _maybe_decode_hex(iv_s) or _b64decode_relaxed(iv_s)
    salt = _maybe_decode_hex(salt_s) or _b64decode_relaxed(salt_s)
    ciphertext = _b64decode_relaxed(ciphertext_s) if _is_probably_base64(ciphertext_s) else ciphertext_s.encode("utf-8")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_len,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    key = kdf.derive(_normalize_password(password).encode("utf-8"))
    return _aes_cbc_decrypt(ciphertext, key, iv)


def _decrypt_envelope_if_present(json_obj: Any, password: str) -> Optional[str]:
    """If json_obj looks like an encrypted envelope, decrypt and return plaintext text."""
    if not isinstance(json_obj, dict):
        return None

    # Case 1: CryptoJS JSON object itself.
    if set(json_obj.keys()) >= {"ct", "iv", "s"}:
        plaintext = _decrypt_cryptojs_json(json_obj, password)
        return plaintext.decode("utf-8", errors="strict")

    # Case 2: Portal-style wrapper { data: <openssl-salted-b64> }
    for key in ("data", "payload", "encryptedData", "encData", "content"):
        value = json_obj.get(key)
        if isinstance(value, str) and _is_probably_base64(value):
            try:
                decoded = _b64decode_relaxed(value)
            except Exception:
                continue
            if decoded.startswith(b"Salted__"):
                plaintext = _decrypt_openssl_salted(decoded, password)
                return plaintext.decode("utf-8", errors="strict")

    # Case 3: PBKDF2-style envelope with params.
    try:
        plaintext = _decrypt_pbkdf2_envelope(json_obj, password)
        return plaintext.decode("utf-8", errors="strict")
    except Exception:
        return None


def _is_json_text(text: str) -> bool:
    if not isinstance(text, str):
        return False
    s = text.lstrip()
    if not s:
        return False
    if s[0] not in "[{":
        return False
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def _decrypt_hexprefix64_base64_ciphertext(encrypted_text: str, password: str) -> str:
    """Decrypt portal format: 64 hex chars + base64 ciphertext.

    Observed in some AIS downloads where the file is not JSON at all.
    """
    encrypted_text = encrypted_text.strip()
    if not _HEX64_B64_RE.fullmatch(encrypted_text):
        raise ValueError("Not hex64+base64 format")

    password = _normalize_password(password)
    password_byte_variants = []
    try:
        password_byte_variants.append(password.encode("utf-8"))
    except Exception:
        pass
    try:
        password_byte_variants.append(password.encode("utf-16le"))
    except Exception:
        pass
    # Preserve order, remove duplicates
    password_byte_variants = list(dict.fromkeys(password_byte_variants))
    prefix_hex = encrypted_text[:64]
    ciphertext_b64 = encrypted_text[64:]

    prefix_bytes = binascii.unhexlify(prefix_hex)
    blob = _b64decode_relaxed(ciphertext_b64)

    # Two observed/likely layouts:
    # A) blob == ciphertext (IV is in the hex prefix or derivation)
    # B) blob == iv(16) + ciphertext (common)
    ciphertext_direct = blob
    iv_from_blob: Optional[bytes] = None
    ciphertext_after_iv: Optional[bytes] = None
    if len(blob) > 16 and (len(blob) - 16) % 16 == 0:
        iv_from_blob = blob[:16]
        ciphertext_after_iv = blob[16:]

    # Try a small set of plausible schemes.
    candidates = []

    iteration_candidates = (1, 10, 100, 500, 1000, 2000, 5000, 10000, 20000, 65536, 100000)
    pbkdf2_algs = (hashes.SHA1(), hashes.SHA256(), hashes.SHA512())
    zero_iv = b"\x00" * 16

    # 1) PBKDF2, salt=prefix(32), derive key+iv
    for alg in pbkdf2_algs:
        for iterations in iteration_candidates:
            for key_len in (16, 24, 32):
                for pw_bytes in password_byte_variants:
                    try:
                        kdf = PBKDF2HMAC(
                            algorithm=alg,
                            length=key_len + 16,
                            salt=prefix_bytes,
                            iterations=iterations,
                            backend=default_backend(),
                        )
                        derived = kdf.derive(pw_bytes)
                        key, iv = derived[:key_len], derived[key_len:key_len + 16]
                        candidates.append((key, iv))
                        candidates.append((key, zero_iv))
                    except Exception:
                        continue

    # 1b) PBKDF2, salt=first16/last16, derive key+iv
    for alg in pbkdf2_algs:
        for iterations in iteration_candidates:
            for key_len in (16, 24, 32):
                for salt in (prefix_bytes[:16], prefix_bytes[16:32]):
                    for pw_bytes in password_byte_variants:
                        try:
                            kdf = PBKDF2HMAC(
                                algorithm=alg,
                                length=key_len + 16,
                                salt=salt,
                                iterations=iterations,
                                backend=default_backend(),
                            )
                            derived = kdf.derive(pw_bytes)
                            key, iv = derived[:key_len], derived[key_len:key_len + 16]
                            candidates.append((key, iv))
                            candidates.append((key, zero_iv))
                        except Exception:
                            continue

    # 2) PBKDF2, salt=first16 / last16, iv=other16
    for alg in pbkdf2_algs:
        for iterations in iteration_candidates:
            for key_len in (16, 24, 32):
                for salt, iv in ((prefix_bytes[:16], prefix_bytes[16:32]), (prefix_bytes[16:32], prefix_bytes[:16])):
                    for pw_bytes in password_byte_variants:
                        try:
                            kdf = PBKDF2HMAC(
                                algorithm=alg,
                                length=key_len,
                                salt=salt,
                                iterations=iterations,
                                backend=default_backend(),
                            )
                            key = kdf.derive(pw_bytes)
                            candidates.append((key, iv))
                            candidates.append((key, zero_iv))
                        except Exception:
                            continue

    # 2b) PBKDF2, salt=prefix(32), iv comes from blob prefix (if present)
    if iv_from_blob is not None:
        for alg in pbkdf2_algs:
            for iterations in iteration_candidates:
                for key_len in (16, 24, 32):
                    for pw_bytes in password_byte_variants:
                        try:
                            kdf = PBKDF2HMAC(
                                algorithm=alg,
                                length=key_len,
                                salt=prefix_bytes,
                                iterations=iterations,
                                backend=default_backend(),
                            )
                            key = kdf.derive(pw_bytes)
                            candidates.append((key, iv_from_blob))
                            candidates.append((key, zero_iv))
                        except Exception:
                            continue

    # 2c) PBKDF2, salt=first16/last16, iv comes from blob prefix (if present)
    if iv_from_blob is not None:
        for alg in pbkdf2_algs:
            for iterations in iteration_candidates:
                for key_len in (16, 24, 32):
                    for salt in (prefix_bytes[:16], prefix_bytes[16:32]):
                        for pw_bytes in password_byte_variants:
                            try:
                                kdf = PBKDF2HMAC(
                                    algorithm=alg,
                                    length=key_len,
                                    salt=salt,
                                    iterations=iterations,
                                    backend=default_backend(),
                                )
                                key = kdf.derive(pw_bytes)
                                candidates.append((key, iv_from_blob))
                                candidates.append((key, zero_iv))
                            except Exception:
                                continue

    # 3) SHA-256(password) key, iv from prefix/blob/zeros (try multiple password encodings)
    for pw_bytes in password_byte_variants:
        key_sha = hashlib.sha256(pw_bytes).digest()
        candidates.append((key_sha, prefix_bytes[:16]))
        candidates.append((key_sha, prefix_bytes[16:32]))
        candidates.append((key_sha, zero_iv))
        if iv_from_blob is not None:
            candidates.append((key_sha, iv_from_blob))

    # 4) MD5(password) expanded key, iv from prefix/blob/zeros (try multiple password encodings)
    for pw_bytes in password_byte_variants:
        md5 = hashlib.md5(pw_bytes).digest()
        md5_key_32 = md5 + hashlib.md5(md5).digest()
        candidates.append((md5_key_32, prefix_bytes[:16]))
        candidates.append((md5_key_32, prefix_bytes[16:32]))
        candidates.append((md5_key_32, zero_iv))
        if iv_from_blob is not None:
            candidates.append((md5_key_32, iv_from_blob))

    # 5) OpenSSL/CryptoJS-style EVP_BytesToKey (MD5), salt from 8/16 bytes of prefix
    salts = [prefix_bytes[:8], prefix_bytes[8:16], prefix_bytes[:16]]
    for pw_bytes in password_byte_variants:
        for salt in salts:
            try:
                key, iv = _evp_bytes_to_key(pw_bytes, salt, 32, 16)
                candidates.append((key, iv))
                candidates.append((key, prefix_bytes[:16]))
                candidates.append((key, prefix_bytes[16:32]))
                candidates.append((key, zero_iv))
                if iv_from_blob is not None:
                    candidates.append((key, iv_from_blob))
            except Exception:
                continue

    def _try_extract_json(plaintext_bytes: bytes) -> Optional[str]:
        # Try direct UTF-8 JSON
        try:
            text = plaintext_bytes.decode("utf-8")
            if _is_json_text(text):
                return json.dumps(json.loads(text), indent=2)
            if text.lstrip().startswith(("{", "[")):
                return text
        except Exception:
            pass

        # Try decompressing (some exports compress before encrypting)
        for decompressor in ("gzip", "zlib"):
            try:
                if decompressor == "gzip":
                    if not plaintext_bytes.startswith(b"\x1f\x8b"):
                        continue
                    decompressed = gzip.decompress(plaintext_bytes)
                else:
                    # zlib header is more variable; try best-effort
                    decompressed = zlib.decompress(plaintext_bytes)
                text = decompressed.decode("utf-8")
                if _is_json_text(text):
                    return json.dumps(json.loads(text), indent=2)
                if text.lstrip().startswith(("{", "[")):
                    return text
            except Exception:
                continue

        return None

    last_error: Optional[Exception] = None
    seen = set()
    attempts = 0
    for key, iv in candidates:
        # Avoid retrying identical key/iv pairs.
        try:
            marker = (key, iv)
            if marker in seen:
                continue
            seen.add(marker)
        except Exception:
            pass

        # Try both ciphertext layouts.
        for ct in (ciphertext_direct, ciphertext_after_iv):
            if ct is None or len(ct) == 0:
                continue

            # A) AES-CBC (with PKCS7 / zero / no padding)
            if len(ct) % 16 == 0:
                try:
                    attempts += 1
                    raw = _aes_cbc_decrypt_raw(ct, key, iv)

                    # Try PKCS7 unpad
                    try:
                        unpadded = _pkcs7_unpad(raw)
                        got = _try_extract_json(unpadded)
                        if got is not None:
                            return got
                    except Exception as e:
                        last_error = e

                    # Try zero padding strip
                    if raw.endswith(b"\x00"):
                        got = _try_extract_json(raw.rstrip(b"\x00"))
                        if got is not None:
                            return got

                    # Try no padding (rare but possible)
                    got = _try_extract_json(raw)
                    if got is not None:
                        return got

                except Exception as e:
                    last_error = e

            # B) AES-CTR / AES-CFB (no padding)
            for stream_mode in ("CTR", "CFB"):
                try:
                    attempts += 1
                    raw = _aes_stream_decrypt(ct, key, iv, stream_mode)
                    got = _try_extract_json(raw)
                    if got is not None:
                        return got
                except Exception as e:
                    last_error = e
                    continue

    layout_hint = "iv+ciphertext" if iv_from_blob is not None else "ciphertext-only"
    raise ValueError(
        "hex64+base64 decryption failed "
        f"(layout={layout_hint}, attempts={attempts}): "
        f"{str(last_error) if last_error else 'unknown error'}"
    )


def decrypt_aes_value(encrypted_value: str, password: str) -> str:
    """
    Decrypt a single AES-encrypted value using password.
    
    Args:
        encrypted_value: Base64 encoded encrypted string
        password: Decryption password (PAN, PAN+DOB, etc.)
    
    Returns:
        Decrypted string
    """
    try:
        password = _normalize_password(password)

        # Decode base64
        encrypted_bytes = _b64decode_relaxed(encrypted_value)

        # OpenSSL salted format (very common): base64("Salted__" + salt + ciphertext)
        if encrypted_bytes.startswith(b"Salted__"):
            plaintext = _decrypt_openssl_salted(encrypted_bytes, password)
            return plaintext.decode("utf-8")
        
        # Derive key from password using SHA-256
        key = hashlib.sha256(password.encode('utf-8')).digest()
        
        # Extract IV (first 16 bytes) and ciphertext
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]
        
        # Decrypt using AES-256-CBC
        plaintext = _aes_cbc_decrypt(ciphertext, key, iv)
        return plaintext.decode('utf-8')
        
    except Exception:
        # Try without IV (some implementations don't use IV)
        try:
            encrypted_bytes = _b64decode_relaxed(encrypted_value)
            key = hashlib.sha256(password.encode('utf-8')).digest()
            
            # Use zero IV
            iv = b'\x00' * 16
            
            plaintext = _aes_cbc_decrypt(encrypted_bytes, key, iv)
            return plaintext.decode('utf-8')
        except:
            pass
        
        # Try MD5 key derivation (older systems)
        try:
            encrypted_bytes = _b64decode_relaxed(encrypted_value)
            key = hashlib.md5(password.encode('utf-8')).digest()
            
            # Pad key to 32 bytes for AES-256
            key = key + hashlib.md5(key).digest()
            
            iv = encrypted_bytes[:16]
            ciphertext = encrypted_bytes[16:]
            
            plaintext = _aes_cbc_decrypt(ciphertext, key, iv)
            return plaintext.decode('utf-8')
        except:
            raise ValueError("Failed to decrypt value with provided password")


def decrypt_json_content(json_obj: dict, password: str) -> dict:
    """
    Recursively decrypt all encrypted values in a JSON object.
    
    Args:
        json_obj: JSON object with encrypted values
        password: Decryption password
    
    Returns:
        JSON object with decrypted values
    """
    if isinstance(json_obj, dict):
        decrypted = {}
        for key, value in json_obj.items():
            if isinstance(value, str) and len(value) > 20 and not value.startswith('{'):
                # Likely an encrypted value (base64 encoded)
                try:
                    decrypted[key] = decrypt_aes_value(value, password)
                except:
                    # If decryption fails, keep original value
                    decrypted[key] = value
            elif isinstance(value, (dict, list)):
                decrypted[key] = decrypt_json_content(value, password)
            else:
                decrypted[key] = value
        return decrypted
    
    elif isinstance(json_obj, list):
        return [decrypt_json_content(item, password) for item in json_obj]
    
    else:
        return json_obj


def decrypt_ais_tis_json(encrypted_data: bytes, password: str) -> str:
    """
    Decrypt AES-encrypted AIS/TIS JSON file using password.
    Handles both fully encrypted files and files with encrypted content.
    """
    try:
        password = _normalize_password(password)

        # First, try to parse as JSON (file structure is readable, content encrypted)
        try:
            json_str = encrypted_data.decode('utf-8')
            json_obj = json.loads(json_str)

            # If this looks like a crypto envelope (common for AIS/TIS portal downloads), decrypt it.
            envelope_plaintext = _decrypt_envelope_if_present(json_obj, password)
            if envelope_plaintext is not None:
                # If decrypted text itself is JSON, pretty-print it.
                try:
                    decrypted_obj = json.loads(envelope_plaintext)
                    return json.dumps(decrypted_obj, indent=2)
                except Exception:
                    return envelope_plaintext
            
            # Check if content appears encrypted (values are base64 strings)
            if _has_encrypted_content(json_obj):
                # Decrypt the content values
                decrypted_obj = decrypt_json_content(json_obj, password)
                return json.dumps(decrypted_obj, indent=2)
            else:
                # Already plain JSON
                return json_str
                
        except (UnicodeDecodeError, json.JSONDecodeError):
            # File itself is encrypted, not just content
            pass

        # Some AIS downloads are a single encrypted blob: 64 hex chars + base64 ciphertext.
        # If the file matches this format, prefer raising the blob-specific error rather than
        # falling back to generic AES guesses.
        try:
            text = encrypted_data.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        if text and _HEX64_B64_RE.fullmatch(text):
            return _decrypt_hexprefix64_base64_ciphertext(text, password)
        
        # Try base64 decoding first (common format for fully encrypted files)
        encrypted_bytes = encrypted_data
        try:
            as_text = encrypted_data.decode("utf-8").strip()
            if _is_probably_base64(as_text):
                encrypted_bytes = _b64decode_relaxed(as_text)
        except Exception:
            pass

        # OpenSSL salted format
        if encrypted_bytes.startswith(b"Salted__"):
            plaintext = _decrypt_openssl_salted(encrypted_bytes, password)
            return plaintext.decode("utf-8")
        
        # Derive key from password using SHA-256
        key = hashlib.sha256(password.encode('utf-8')).digest()
        
        # Extract IV (first 16 bytes) and ciphertext
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]
        
        # Decrypt using AES-256-CBC
        plaintext = _aes_cbc_decrypt(ciphertext, key, iv)
        return plaintext.decode('utf-8')
        
    except Exception as e:
        # Try alternative methods
        try:
            return _decrypt_alternative_methods(encrypted_data, password)
        except:
            root = str(e).replace("\n", " ").strip()
            raise ValueError(
                "Failed to decrypt AIS/TIS file. "
                "If this is a portal download, the password is usually PAN (uppercase) + DOB (DDMMYYYY). "
                f"Root error: {root}"
            )


def _has_encrypted_content(json_obj: dict) -> bool:
    """Check if JSON object contains encrypted content."""
    if isinstance(json_obj, dict):
        for key, value in json_obj.items():
            if isinstance(value, str) and len(value) > 50:
                # Check if it looks like base64
                try:
                    base64.b64decode(value)
                    # If it decodes and is long, likely encrypted
                    if len(value) > 50 and not value.startswith('{'):
                        return True
                except:
                    pass
            elif isinstance(value, (dict, list)):
                if _has_encrypted_content(value):
                    return True
    elif isinstance(json_obj, list):
        for item in json_obj:
            if _has_encrypted_content(item):
                return True
    return False


def _decrypt_alternative_methods(encrypted_data: bytes, password: str) -> str:
    """Try alternative decryption methods."""
    methods = [
        # Portal blob format: hex64 + base64 (handled as text)
        lambda: _decrypt_hexprefix64_base64_ciphertext(encrypted_data.decode("utf-8").strip(), password),
        lambda: _decrypt_with_padded_key(encrypted_data, password),
        lambda: _decrypt_with_md5_key(encrypted_data, password),
        lambda: _decrypt_with_zero_iv(encrypted_data, password),
    ]
    
    for method in methods:
        try:
            return method()
        except:
            continue
    
    raise ValueError("All decryption methods failed")


def _decrypt_with_padded_key(encrypted_data: bytes, password: str) -> str:
    """Decrypt with password padded to 32 bytes."""
    key = password.encode('utf-8')
    if len(key) < 32:
        key = key + b'\x00' * (32 - len(key))
    else:
        key = key[:32]
    
    password = _normalize_password(password)
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
    except Exception:
        encrypted_bytes = encrypted_data
    
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    
    plaintext = _aes_cbc_decrypt(ciphertext, key, iv)
    return plaintext.decode('utf-8')


def _decrypt_with_md5_key(encrypted_data: bytes, password: str) -> str:
    """Decrypt with MD5-derived key."""
    password = _normalize_password(password)
    key = hashlib.md5(password.encode('utf-8')).digest()
    key = key + hashlib.md5(key).digest()  # Extend to 32 bytes
    
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
    except Exception:
        encrypted_bytes = encrypted_data
    
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    
    plaintext = _aes_cbc_decrypt(ciphertext, key, iv)
    return plaintext.decode('utf-8')


def _decrypt_with_zero_iv(encrypted_data: bytes, password: str) -> str:
    """Decrypt with zero IV."""
    password = _normalize_password(password)
    key = hashlib.sha256(password.encode('utf-8')).digest()
    
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
    except Exception:
        encrypted_bytes = encrypted_data
    
    iv = b'\x00' * 16
    
    plaintext = _aes_cbc_decrypt(encrypted_bytes, key, iv)
    return plaintext.decode('utf-8')


def decrypt_ais_tis_file(file_path: str, password: str) -> str:
    """
    Read and decrypt an encrypted AIS/TIS JSON file.
    
    Args:
        file_path: Path to encrypted JSON file
        password: Decryption password (usually PAN + DOB)
    
    Returns:
        Decrypted JSON string
    """
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    
    return decrypt_ais_tis_json(encrypted_data, password)


def is_encrypted_file(file_path: str) -> bool:
    """Check if file appears to be encrypted (not plain JSON or has encrypted content)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Try to parse as JSON
        try:
            json_obj = json.loads(content)
            # Encrypted envelope (CryptoJS/OpenSSL/PBKDF2) should still trigger password prompt.
            if isinstance(json_obj, dict):
                keys = set(json_obj.keys())
                if {"ct", "iv", "s"}.issubset(keys):
                    return True
                if any(k in keys for k in ("ciphertext", "salt", "iterations", "iter", "encryptedData", "encData", "payload", "data", "content")):
                    # If it contains a long base64 payload, treat as encrypted.
                    for k in ("ciphertext", "data", "payload", "encryptedData", "encData", "content"):
                        v = json_obj.get(k)
                        if isinstance(v, str) and len(v) > 32 and _is_probably_base64(v):
                            return True

            # Check if content has encrypted values
            return _has_encrypted_content(json_obj)
        except json.JSONDecodeError:
            # Can't parse as JSON, likely fully encrypted
            return True
            
    except UnicodeDecodeError:
        # Can't read as text, definitely encrypted
        return True
    except:
        return True
