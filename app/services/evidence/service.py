"""
Photographic Evidence Ingestion and Validation Service.

Enforces strict security boundaries:
- MIME type and magic bytes verification
- PIL decompression bomb limits & integrity verify
- Maximum dimension & file size limits
- Polyglot & executable file rejection
- Filename sanitization
- Authoritative PostgreSQL metadata persistence
"""
from __future__ import annotations

import datetime
import hashlib
import io
from pathlib import Path
import uuid

from PIL import Image
from sqlalchemy.orm import Session
import structlog

from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.models.evidence import IncidentEvidence
from app.models.user import User

logger = structlog.get_logger("risksetu.evidence.service")

# Pillow Decompression Bomb Safety
Image.MAX_IMAGE_PIXELS = 64_000_000

ALLOWED_MIME_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/jpg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

DISALLOWED_SIGNATURES = [
    b"MZ",           # Windows PE executable
    b"\x7fELF",      # Linux ELF executable
    b"#!/bin/",      # Unix shell script
    b"<?php",        # PHP script
    b"<script",      # HTML/JS script
]

MAX_DIMENSION = 8000


class EvidenceService:
    """Service validating, storing, and indexing emergency photographic evidence."""

    def __init__(self) -> None:
        settings = get_settings()
        self.upload_dir = Path(settings.evidence_upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = settings.evidence_max_size_bytes

    def validate_image_file(
        self,
        file_bytes: bytes,
        declared_content_type: str,
        original_filename: str,
    ) -> str:
        """Validate file size, magic bytes, PIL structure, and absence of malicious payloads."""
        # 1. File size check
        if len(file_bytes) == 0:
            raise ValidationAppError("Uploaded evidence file is empty.")

        if len(file_bytes) > self.max_size_bytes:
            raise ValidationAppError(
                f"File size ({len(file_bytes)} bytes) exceeds maximum limit of {self.max_size_bytes} bytes."
            )

        # 2. MIME type check
        content_type = declared_content_type.lower().strip()
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValidationAppError(
                f"Unsupported media type '{declared_content_type}'. Allowed types: JPEG, PNG, WebP."
            )

        # 3. Magic bytes inspection
        expected_signatures = ALLOWED_MIME_TYPES[content_type]
        has_magic = any(file_bytes.startswith(sig) for sig in expected_signatures)
        if content_type == "image/webp":
            # WebP must have RIFF header and WEBP chunk type at bytes 8-12
            has_magic = file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"

        if not has_magic:
            raise ValidationAppError(
                f"File signature mismatch: file content does not match declared MIME type '{declared_content_type}'."
            )

        # 4. Executable / polyglot marker scan
        for dis in DISALLOWED_SIGNATURES:
            if dis in file_bytes[:1024]:
                logger.warning("executable_signature_detected_in_evidence", signature=dis)
                raise ValidationAppError("Uploaded file contains disallowed executable or script signatures.")

        # 5. Pillow structural verification
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
        except Exception as exc:
            logger.warning("image_integrity_verification_failed", error=str(exc))
            raise ValidationAppError("Corrupt or invalid image file structure.") from exc

        # 6. Dimension validation
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
                if width > MAX_DIMENSION or height > MAX_DIMENSION:
                    raise ValidationAppError(
                        f"Image dimensions ({width}x{height}) exceed maximum allowed limit of {MAX_DIMENSION}x{MAX_DIMENSION}."
                    )
                if width < 10 or height < 10:
                    raise ValidationAppError("Image dimensions are too small to serve as valid photographic evidence.")
        except ValidationAppError:
            raise
        except Exception as exc:
            raise ValidationAppError("Failed to verify image dimensions.") from exc

        # Return standardized extension
        if "png" in content_type:
            return "png"
        if "webp" in content_type:
            return "webp"
        return "jpg"

    def store_evidence(
        self,
        db: Session,
        owner: User,
        file_bytes: bytes,
        original_filename: str,
        declared_content_type: str,
        latitude: float | None = None,
        longitude: float | None = None,
        captured_at: datetime.datetime | None = None,
        incident_id: uuid.UUID | None = None,
        sos_id: uuid.UUID | None = None,
    ) -> IncidentEvidence:
        """Validate, persist to disk, and authoritatively record evidence in PostgreSQL."""
        ext = self.validate_image_file(file_bytes, declared_content_type, original_filename)

        # Compute SHA256
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        # Sanitize filename by storing under a UUID
        evidence_id = uuid.uuid4()
        storage_filename = f"{evidence_id}.{ext}"
        storage_path = self.upload_dir / storage_filename

        try:
            with open(storage_path, "wb") as f:
                f.write(file_bytes)
        except OSError as exc:
            logger.error("failed_to_write_evidence_file", path=str(storage_path), error=str(exc))
            raise ValidationAppError("Could not persist evidence file to storage.") from exc

        evidence = IncidentEvidence(
            id=evidence_id,
            owner_user_id=owner.id,
            incident_id=incident_id,
            sos_id=sos_id,
            storage_key=str(storage_path),
            content_type=declared_content_type,
            size_bytes=len(file_bytes),
            sha256=sha256_hash,
            captured_at=captured_at or datetime.datetime.now(datetime.timezone.utc),
            latitude=latitude,
            longitude=longitude,
            upload_status="STORED",
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        logger.info(
            "incident_evidence_stored",
            evidence_id=str(evidence.id),
            owner_id=str(owner.id),
            size_bytes=len(file_bytes),
            sha256=sha256_hash,
        )

        return evidence

    def get_evidence(
        self,
        db: Session,
        evidence_id: uuid.UUID,
    ) -> IncidentEvidence | None:
        """Retrieve authoritative evidence metadata by ID."""
        return db.get(IncidentEvidence, evidence_id)
