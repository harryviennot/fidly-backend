"""
Certificate Manager for per-business Apple Pass Type ID certificates.

Handles:
- .p12 extraction (signer cert, key, APNs combined)
- AES-256-GCM encryption/decryption of PEM data
- Two-layer caching: in-memory (5min TTL) + Redis encrypted blobs (1hr TTL)
- Temp file management for aioapns (requires file path)
"""

import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    pkcs12,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory cache: {business_id: (expiry_timestamp, cert_tuple)}
_cert_cache: dict[str, tuple[float, tuple[str, bytes, bytes, bytes]]] = {}
_MEMORY_TTL = 300  # 5 minutes

# Redis cache TTL
_REDIS_TTL = 3600  # 1 hour
_REDIS_KEY_PREFIX = "cert:"


class CertificateManager:
    """Manages per-business certificate storage, encryption, and retrieval."""

    def __init__(self, encryption_key: bytes):
        self._aesgcm = AESGCM(encryption_key)

    def extract_from_p12(
        self, p12_data: bytes, password: str | None = None
    ) -> tuple[bytes, bytes, bytes]:
        """Extract signer cert, key, and APNs combined PEM from a .p12 file.

        Args:
            p12_data: Raw .p12 file bytes
            password: Optional password for the .p12 file

        Returns:
            (signer_cert_pem, signer_key_pem, apns_combined_pem)
        """
        pwd = password.encode() if password else None
        private_key, certificate, _ = pkcs12.load_key_and_certificates(p12_data, pwd)

        if not private_key or not certificate:
            raise ValueError("P12 file must contain both a private key and certificate")

        from cryptography.hazmat.primitives.serialization import PrivateFormat
        signer_key_pem = private_key.private_bytes(
            Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
        )
        signer_cert_pem = certificate.public_bytes(Encoding.PEM)

        # APNs combined = cert + key in one file
        apns_combined_pem = signer_cert_pem + signer_key_pem

        return signer_cert_pem, signer_key_pem, apns_combined_pem

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data with AES-256-GCM.

        Returns IV (12 bytes) + ciphertext+tag as a single blob.
        """
        iv = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(iv, data, None)
        return iv + ciphertext

    def decrypt(self, encrypted_blob: bytes) -> bytes:
        """Decrypt AES-256-GCM encrypted blob.

        Expects IV (first 12 bytes) + ciphertext+tag.
        """
        iv = encrypted_blob[:12]
        ciphertext = encrypted_blob[12:]
        return self._aesgcm.decrypt(iv, ciphertext, None)

    def get_certs_for_business(
        self, business_id: str
    ) -> tuple[str, bytes, bytes, bytes]:
        """Get certificate data for a business.

        Returns:
            (pass_type_identifier, signer_cert_pem, signer_key_pem, apns_combined_pem)

        Fallback chain:
        1. If per_business_certs_enabled is False → shared certs from files
        2. If enabled: in-memory cache → Redis → Supabase DB
        3. If enabled but no assignment → fall back to shared certs (migration safety)
        """
        if not settings.per_business_certs_enabled:
            return self._get_shared_certs()

        # Check in-memory cache
        cached = self._get_from_memory_cache(business_id)
        if cached:
            return cached

        # Check Redis cache
        cached = self._get_from_redis_cache(business_id)
        if cached:
            self._set_memory_cache(business_id, cached)
            return cached

        # Load from database
        from app.repositories.pass_type_id import PassTypeIdRepository

        record = PassTypeIdRepository.get_for_business(business_id)
        if not record:
            # Business has no pool assignment yet — fall back to shared certs
            logger.info(
                f"No pass_type_id assigned for business {business_id}, using shared certs"
            )
            return self._get_shared_certs()

        cert_tuple = self._decrypt_record(record)
        self._set_memory_cache(business_id, cert_tuple)
        self._set_redis_cache(business_id, record)

        return cert_tuple

    @contextmanager
    def apns_cert_tempfile(self, apns_pem: bytes):
        """Context manager yielding a temp file path containing APNs PEM data.

        aioapns requires a file path, so we write to a temp file per push batch.
        OS guarantees unique path; auto-deleted on exit.
        """
        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pem", delete=True
        )
        try:
            tmp.write(apns_pem)
            tmp.flush()
            os.chmod(tmp.name, 0o600)
            yield tmp.name
        finally:
            tmp.close()

    def _get_shared_certs(self) -> tuple[str, bytes, bytes, bytes]:
        """Load shared certs from Doppler-written files (dev/staging path)."""
        return (
            settings.apple_pass_type_id,
            Path(settings.cert_path).read_bytes(),
            Path(settings.key_path).read_bytes(),
            Path(settings.apns_cert_path).read_bytes(),
        )

    def _get_from_memory_cache(
        self, business_id: str
    ) -> Optional[tuple[str, bytes, bytes, bytes]]:
        """Check in-memory cache (5min TTL)."""
        entry = _cert_cache.get(business_id)
        if entry and entry[0] > time.time():
            return entry[1]
        if entry:
            del _cert_cache[business_id]
        return None

    def _set_memory_cache(
        self, business_id: str, cert_tuple: tuple[str, bytes, bytes, bytes]
    ) -> None:
        """Store in in-memory cache."""
        _cert_cache[business_id] = (time.time() + _MEMORY_TTL, cert_tuple)

    def _get_from_redis_cache(
        self, business_id: str
    ) -> Optional[tuple[str, bytes, bytes, bytes]]:
        """Check Redis cache (1hr TTL). Stores encrypted blobs."""
        try:
            import redis as redis_lib

            from app.services.strip_cache import get_redis

            r = get_redis()
            data = r.get(f"{_REDIS_KEY_PREFIX}{business_id}")
            if not data:
                return None

            record = json.loads(data)
            return self._decrypt_record(record)
        except Exception as e:
            logger.debug(f"Redis cert cache miss for {business_id}: {e}")
            return None

    def _set_redis_cache(self, business_id: str, record: dict) -> None:
        """Store encrypted DB record in Redis."""
        try:
            from app.services.strip_cache import get_redis

            r = get_redis()
            # Store the raw DB record (already encrypted blobs)
            cache_data = json.dumps(
                {
                    "identifier": record["identifier"],
                    "team_id": record["team_id"],
                    "signer_cert_encrypted": _encode_blob(
                        record["signer_cert_encrypted"]
                    ),
                    "signer_key_encrypted": _encode_blob(
                        record["signer_key_encrypted"]
                    ),
                    "apns_combined_encrypted": _encode_blob(
                        record["apns_combined_encrypted"]
                    ),
                }
            )
            r.setex(f"{_REDIS_KEY_PREFIX}{business_id}", _REDIS_TTL, cache_data)
        except Exception as e:
            logger.warning(f"Failed to set Redis cert cache: {e}")

    def _decrypt_record(
        self, record: dict
    ) -> tuple[str, bytes, bytes, bytes]:
        """Decrypt a pass_type_id DB record into usable PEM bytes."""
        signer_cert = self.decrypt(
            _decode_blob(record["signer_cert_encrypted"])
        )
        signer_key = self.decrypt(
            _decode_blob(record["signer_key_encrypted"])
        )
        apns_combined = self.decrypt(
            _decode_blob(record["apns_combined_encrypted"])
        )
        return record["identifier"], signer_cert, signer_key, apns_combined


def _encode_blob(data) -> str:
    """Encode bytes to base64 string for JSON/Redis serialization."""
    import base64
    if isinstance(data, str):
        return data
    if isinstance(data, memoryview):
        data = bytes(data)
    return base64.b64encode(data).decode()


def _decode_blob(data) -> bytes:
    """Decode base64 string (from Supabase BYTEA or Redis cache) back to bytes."""
    import base64
    if isinstance(data, (bytes, memoryview)):
        data = bytes(data) if isinstance(data, memoryview) else data
        # Raw binary — return as-is
        try:
            data.decode("ascii")
        except UnicodeDecodeError:
            return data
        data = data.decode("ascii")
    return base64.b64decode(data)


# Singleton
_manager: Optional[CertificateManager] = None


def get_certificate_manager() -> CertificateManager:
    """Get or create the singleton CertificateManager."""
    global _manager
    if _manager is None:
        key_hex = settings.cert_encryption_key
        if not key_hex:
            # No encryption key configured — create a dummy manager
            # that only serves shared certs (dev mode)
            key_hex = "0" * 64
        encryption_key = bytes.fromhex(key_hex)
        _manager = CertificateManager(encryption_key)
    return _manager
