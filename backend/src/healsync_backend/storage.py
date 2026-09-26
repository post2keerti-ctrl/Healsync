"""Private Firebase Storage conventions for original medical documents."""
from __future__ import annotations

from pathlib import PurePosixPath


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def document_storage_path(user_id: str, document_id: str, filename: str) -> str:
    """Return a non-user-controlled path under a private per-user prefix."""
    suffix = PurePosixPath(filename).suffix.lower() or ".bin"
    return f"private/users/{user_id}/documents/{document_id}{suffix}"


def validate_document(content_type: str | None, size_bytes: int) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Only JPEG, PNG, WebP, and PDF documents are supported")
    if size_bytes <= 0 or size_bytes > MAX_DOCUMENT_BYTES:
        raise ValueError("Document size must be between 1 byte and 10 MB")
