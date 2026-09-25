"""Dataset/file service (Phase 7): storage, metadata and cleanup."""

import hashlib
import io
import os

import pytest
from werkzeug.datastructures import FileStorage

from app.models import BusinessObject, Dataset, ManagedFile
from app.services import ServiceError, datasets


def _revision(session, number="DOC-600"):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
        .current_revision
    )


def _storage(content=b"hello", filename="notes.txt", content_type="text/plain"):
    return FileStorage(
        stream=io.BytesIO(content), filename=filename, content_type=content_type
    )


def test_attach_file_stores_bytes_and_metadata(session):
    revision = _revision(session)

    managed = datasets.attach_file(
        revision,
        _storage(b"hello world"),
        dataset_name="Docs",
        dataset_type="Document",
        session=session,
    )

    assert managed.dataset.revision_id == revision.id
    assert managed.dataset.name == "Docs"
    assert managed.file_name == "notes.txt"
    assert managed.file_size == 11
    assert managed.mime_type == "text/plain"
    assert managed.checksum == hashlib.sha256(b"hello world").hexdigest()

    path = datasets.file_path(managed)
    assert os.path.exists(path)
    with open(path, "rb") as handle:
        assert handle.read() == b"hello world"
    assert datasets.checksum(path) == managed.checksum


def test_attach_file_reuses_named_dataset(session):
    revision = _revision(session)
    first = datasets.attach_file(
        revision, _storage(b"one", "one.txt"), dataset_name="Docs", session=session
    )
    second = datasets.attach_file(
        revision, _storage(b"two", "two.txt"), dataset_name="Docs", session=session
    )
    assert first.dataset_id == second.dataset_id


def test_attach_file_defaults_dataset_name(session):
    revision = _revision(session)
    managed = datasets.attach_file(revision, _storage(), session=session)
    assert managed.dataset.name == "Attachments"


def test_attach_file_rejects_disallowed_extension(session):
    revision = _revision(session)
    with pytest.raises(ServiceError):
        datasets.attach_file(
            revision, _storage(b"x", filename="evil.exe"), session=session
        )


def test_attach_file_requires_a_file(session):
    revision = _revision(session)
    with pytest.raises(ServiceError):
        datasets.attach_file(
            revision, _storage(b"", filename=""), session=session
        )


def test_attach_file_rejects_oversize(session):
    revision = _revision(session)
    from flask import current_app

    original = current_app.config["MAX_CONTENT_LENGTH"]
    current_app.config["MAX_CONTENT_LENGTH"] = 4
    try:
        with pytest.raises(ServiceError):
            datasets.attach_file(
                revision, _storage(b"too big"), session=session
            )
    finally:
        current_app.config["MAX_CONTENT_LENGTH"] = original


def test_delete_file_removes_bytes_and_row(session):
    revision = _revision(session)
    managed = datasets.attach_file(revision, _storage(), session=session)
    managed_id = managed.id
    path = datasets.file_path(managed)
    assert os.path.exists(path)

    assert datasets.delete_file(managed, session=session) is True

    assert not os.path.exists(path)
    assert session.query(ManagedFile).filter_by(id=managed_id).one_or_none() is None


def test_delete_dataset_removes_every_file(session):
    revision = _revision(session)
    dataset = datasets.attach_file(
        revision, _storage(b"one", "one.txt"), session=session
    ).dataset
    datasets.add_file(dataset, _storage(b"two", "two.txt"), session=session)
    paths = [datasets.file_path(f) for f in dataset.files]
    assert len(paths) == 2
    assert all(os.path.exists(path) for path in paths)

    removed = datasets.delete_dataset(dataset, session=session)

    assert removed == 2
    assert not any(os.path.exists(path) for path in paths)
    assert session.query(Dataset).filter_by(id=dataset.id).one_or_none() is None


def test_seeded_file_bytes_exist(session):
    managed = session.query(ManagedFile).first()
    assert managed is not None
    assert managed.file
    assert managed.checksum
    assert managed.file_size and managed.file_size > 0
    assert os.path.exists(datasets.file_path(managed))
    assert datasets.checksum(datasets.file_path(managed)) == managed.checksum


def test_shipped_upload_config_is_safe():
    """Uploads stay out of the web-served static tree and are type-restricted."""
    import config

    assert config.FILE_ALLOWED_EXTENSIONS
    assert "txt" in config.FILE_ALLOWED_EXTENSIONS
    assert "static" not in config.UPLOAD_FOLDER.replace("\\", "/")
    assert config.MAX_CONTENT_LENGTH and config.MAX_CONTENT_LENGTH > 0