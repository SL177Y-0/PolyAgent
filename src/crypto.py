"""Encryption utilities for securing sensitive configuration data.

This module provides encryption/decryption for sensitive data like private keys
that are stored in bot configuration files. Uses Fernet symmetric encryption.

The encryption key is derived from a machine-specific secret or can be 
provided by the user. If no key exists, one is generated and stored locally.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Directory for storing encryption key
KEY_FILE = Path("data/.encryption_key")


def _get_machine_id() -> bytes:
    """Get a machine-specific identifier for key derivation.
    
    Uses a combination of factors to create a stable machine ID.
    """
    # Use username + home directory as a simple machine identifier
    # This ensures the key is tied to this specific user/machine
    user = os.environ.get("USERNAME", os.environ.get("USER", "default"))
    home = str(Path.home())
    machine_str = f"{user}:{home}:polyagent-v1"
    return machine_str.encode('utf-8')


def _derive_key(password: bytes, salt: bytes) -> bytes:
    """Derive a Fernet key from password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # High iteration count for security
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key


def _get_or_create_key() -> bytes:
    """Get existing encryption key or create a new one.
    
    The key is stored in a local file and derived from machine-specific data.
    """
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if KEY_FILE.exists():
        try:
            with open(KEY_FILE, "rb") as f:
                data = f.read()
            # File contains: salt (32 bytes) + encrypted_key_check (variable)
            if len(data) >= 32:
                salt = data[:32]
                key = _derive_key(_get_machine_id(), salt)
                return key
        except Exception as e:
            logger.warning(f"Failed to load encryption key, generating new one: {e}")
    
    # Generate new salt and key
    salt = secrets.token_bytes(32)
    key = _derive_key(_get_machine_id(), salt)
    
    # Save salt to file
    with open(KEY_FILE, "wb") as f:
        f.write(salt)
    
    # Set restrictive permissions (owner read/write only)
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass  # Windows may not support chmod
    
    logger.info("Generated new encryption key")
    return key


# Global Fernet instance (lazy initialized)
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """Get or create the Fernet encryption instance."""
    global _fernet
    if _fernet is None:
        key = _get_or_create_key()
        _fernet = Fernet(key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a sensitive value.
    
    Args:
        plaintext: The sensitive string to encrypt
        
    Returns:
        Encrypted string (base64 encoded with 'enc:' prefix)
    """
    if not plaintext:
        return plaintext
    
    # Don't double-encrypt
    if plaintext.startswith("enc:"):
        return plaintext
    
    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plaintext.encode('utf-8'))
        return f"enc:{encrypted.decode('utf-8')}"
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Failed to encrypt value: {e}")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a sensitive value.
    
    Args:
        ciphertext: The encrypted string (with 'enc:' prefix)
        
    Returns:
        Decrypted plaintext string
    """
    if not ciphertext:
        return ciphertext
    
    # Not encrypted
    if not ciphertext.startswith("enc:"):
        return ciphertext
    
    try:
        fernet = _get_fernet()
        encrypted_data = ciphertext[4:]  # Remove 'enc:' prefix
        decrypted = fernet.decrypt(encrypted_data.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.error("Decryption failed - invalid token (key may have changed)")
        raise ValueError("Failed to decrypt: invalid encryption key")
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise ValueError(f"Failed to decrypt value: {e}")


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return value.startswith("enc:") if value else False


def encrypt_sensitive_fields(data: dict, fields: list[str]) -> dict:
    """Encrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing sensitive data
        fields: List of field names to encrypt
        
    Returns:
        New dictionary with specified fields encrypted
    """
    result = data.copy()
    for field in fields:
        if field in result and result[field]:
            result[field] = encrypt_value(str(result[field]))
    return result


def decrypt_sensitive_fields(data: dict, fields: list[str]) -> dict:
    """Decrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary containing encrypted data
        fields: List of field names to decrypt
        
    Returns:
        New dictionary with specified fields decrypted
    """
    result = data.copy()
    for field in fields:
        if field in result and result[field]:
            try:
                result[field] = decrypt_value(str(result[field]))
            except ValueError as e:
                logger.warning(f"Failed to decrypt field {field}: {e}")
                # Keep the original value if decryption fails
    return result
