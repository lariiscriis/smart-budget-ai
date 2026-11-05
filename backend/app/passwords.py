"""scrypt with a per-password random salt; no secrets or extra packages needed."""
import hashlib
import hmac
import secrets
from threading import BoundedSemaphore

_slots = BoundedSemaphore(2)
N, R, P = 2 ** 17, 8, 1


def _derive(password: str, salt: bytes) -> bytes:
    with _slots:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=64, maxmem=256 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${N}${R}${P}${salt.hex()}${_derive(password, salt).hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if (algorithm, int(n), int(r), int(p)) != ("scrypt", N, R, P):
            return False
        salt_bytes = bytes.fromhex(salt)
        if len(salt_bytes) != 16 or len(expected) != 128:
            return False
        return hmac.compare_digest(_derive(password, salt_bytes).hex(), expected)
    except (ValueError, TypeError):
        return False
