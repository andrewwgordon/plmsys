"""Dataset/file service (Phase 7).

Owns the whole lifecycle of a managed file: validating the upload, choosing a
safe unique name, storing the bytes under ``UPLOAD_FOLDER`` (which is **outside**
the web-served static tree), deriving size/MIME/SHA-256 server-side, and
removing the bytes whenever a ``ManagedFile`` or its ``Dataset`` is deleted.

Views never touch files directly; they call this service so the guards cannot be
bypassed (see ``docs/plan.md`` Phase 7).
"""

import hashlib
import mimetypes
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Dataset, ManagedFile
from . import ServiceError

_CHUNK = 1024 * 1024
_DEFAULT_DATASET = "Attachments"
_DEFAULT_TYPE = "Attachment"


def _session(session):
    return session if session is not None else db.session


def upload_folder() -> str:
    folder = current_app.config.get("UPLOAD_FOLDER")
    if not folder:
        raise ServiceError("UPLOAD_FOLDER is not configured.")
    return folder


def file_path(managed_file) -> str:
    """Absolute path of a managed file's bytes."""
    return os.path.join(upload_folder(), managed_file.file or "")


def allowed_extensions() -> set:
    return {
        str(extension).lower().lstrip(".")
        for extension in current_app.config.get("FILE_ALLOWED_EXTENSIONS", set())
    }


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def checksum(path: str) -> str:
    """SHA-256 hex digest of the file at ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_upload(upload) -> str:
    """Return the original filename, or raise :class:`ServiceError`."""
    filename = getattr(upload, "filename", "") or ""
    if not filename:
        raise ServiceError("A file is required.")
    allowed = allowed_extensions()
    extension = _extension(filename)
    if allowed and extension not in allowed:
        raise ServiceError(
            f"File type {extension!r} is not allowed."
            if extension
            else "The file must have an extension."
        )
    return filename


def _store(upload, original_name: str):
    """Persist ``upload`` under a unique safe name.

    Returns ``(stored_name, size, mime_type, sha256)``.
    """
    folder = upload_folder()
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(original_name) or "file"
    stored_name = f"{uuid.uuid4().hex}_sep_{safe_name}"
    path = os.path.join(folder, stored_name)

    max_bytes = current_app.config.get("MAX_CONTENT_LENGTH")
    digest = hashlib.sha256()
    size = 0
    try:
        with open(path, "wb") as target:
            while True:
                chunk = upload.stream.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if max_bytes is not None and size > int(max_bytes):
                    raise ServiceError(
                        "The file exceeds the maximum allowed size."
                    )
                digest.update(chunk)
                target.write(chunk)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
    finally:
        try:
            upload.stream.seek(0)
        except (AttributeError, OSError):
            pass

    mime_type = (
        getattr(upload, "mimetype", None)
        or mimetypes.guess_type(original_name)[0]
        or "application/octet-stream"
    )
    return stored_name, size, mime_type, digest.hexdigest()


def add_file(dataset, upload, *, session=None) -> ManagedFile:
    """Store ``upload`` and attach it to ``dataset``."""
    session = _session(session)
    if dataset is None or dataset.revision is None:
        raise ServiceError("A dataset must belong to a revision.")
    original_name = _validate_upload(upload)
    stored_name, size, mime_type, digest = _store(upload, original_name)

    managed_file = ManagedFile(
        dataset=dataset,
        file_name=original_name,
        mime_type=mime_type,
        file=stored_name,
        file_size=size,
        checksum=digest,
    )
    session.add(managed_file)
    session.flush()
    return managed_file


def attach_file(
    revision,
    upload,
    dataset_name=None,
    dataset_type=None,
    created_by=None,
    *,
    session=None,
) -> ManagedFile:
    """Attach ``upload`` to ``revision``, reusing the named dataset if present.

    ``created_by`` is accepted for call-site compatibility (the domain model has
    no user FK) and is not stored.
    """
    session = _session(session)
    if revision is None:
        raise ServiceError("A revision is required.")

    name = (dataset_name or "").strip() or _DEFAULT_DATASET
    dataset = (
        session.query(Dataset)
        .filter_by(revision_id=revision.id, name=name)
        .one_or_none()
    )
    if dataset is None:
        dataset = Dataset(
            revision=revision,
            name=name,
            dataset_type=(dataset_type or "").strip() or _DEFAULT_TYPE,
        )
        session.add(dataset)
        session.flush()
    return add_file(dataset, upload, session=session)


def delete_file(managed_file, *, session=None) -> bool:
    """Delete one managed file's bytes and row. Returns whether one existed."""
    session = _session(session)
    if managed_file is None:
        return False
    path = file_path(managed_file)
    if managed_file.file and os.path.exists(path):
        os.remove(path)
    session.delete(managed_file)
    session.flush()
    return True


def delete_dataset(dataset, *, session=None) -> int:
    """Delete a dataset and every physical file it owns."""
    session = _session(session)
    files = list(dataset.files)
    for managed_file in files:
        path = file_path(managed_file)
        if managed_file.file and os.path.exists(path):
            os.remove(path)
        # Detach from the collection so the cascade does not try to DELETE the
        # row a second time (delete-orphan schedules the row delete).
        dataset.files.remove(managed_file)
    session.delete(dataset)
    session.flush()
    return len(files)


__all__ = [
    "add_file",
    "allowed_extensions",
    "attach_file",
    "checksum",
    "delete_dataset",
    "delete_file",
    "file_path",
    "upload_folder",
]