"""
Fernet-based encryption for 2FA secrets.

Key file is auto-generated on first use at data/2fa.key.
"""

import logging
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

KEY_FILE = Path("data/2fa.key")


def _load_or_create_key() -> bytes:
    """Load encryption key from file, or generate and save a new one."""
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes().strip()
        logger.info("Loaded encryption key from %s", KEY_FILE)
        return key

    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    logger.info("Generated new encryption key at %s", KEY_FILE)
    return key


_fernet = Fernet(_load_or_create_key())


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret, returns base64-encoded ciphertext string."""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plaintext secret."""
    return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Check if a value looks like a Fernet token (starts with gAAAAA)."""
    return value.startswith("gAAAAA")
