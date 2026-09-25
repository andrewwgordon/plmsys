"""Phase 7 attachments: upload, list, download, remove and permissions."""

import io

from app.models import BusinessObject, ManagedFile


def _revision_id(session, number="DOC-600"):
    return (
        session.query(BusinessObject)
        .filter_by(object_number=number)
        .one()
        .current_revision_id
    )


def _upload(client, revision_id, filename, content=b"body", **extra):
    data = {
        "file": (io.BytesIO(content), filename),
        "dataset_name": extra.get("dataset_name", "Specs"),
        "dataset_type": extra.get("dataset_type", "Document"),
    }
    return client.post(
        f"/revision/{revision_id}/attach",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Upload + download
# ---------------------------------------------------------------------------


def test_attach_and_download(db_session, admin_client):
    revision_id = _revision_id(db_session)

    response = _upload(admin_client, revision_id, "spec.txt", b"attachment body")

    assert response.status_code == 200
    assert b"File attached" in response.data

    db_session.expire_all()
    managed = db_session.query(ManagedFile).filter_by(file_name="spec.txt").one()
    assert managed.file  # managed filename
    assert managed.file_size == len(b"attachment body")
    assert managed.checksum

    download = admin_client.get(f"/file/{managed.id}/download")
    assert download.status_code == 200
    assert download.data == b"attachment body"
    assert "attachment" in download.headers["Content-Disposition"].lower()
    assert "spec.txt" in download.headers["Content-Disposition"]


def test_attach_rejects_disallowed_extension(db_session, admin_client):
    revision_id = _revision_id(db_session)

    response = _upload(admin_client, revision_id, "evil.exe", b"x")

    assert b"not allowed" in response.data
    assert db_session.query(ManagedFile).filter_by(file_name="evil.exe").count() == 0


def test_download_unknown_file_is_404(admin_client):
    assert admin_client.get("/file/999999/download").status_code == 404


# ---------------------------------------------------------------------------
# Attachments page + remove
# ---------------------------------------------------------------------------


def test_attachments_page_lists_seeded_file(db_session, admin_client):
    revision_id = _revision_id(db_session)

    body = admin_client.get(
        f"/revision/{revision_id}/attachments"
    ).get_data(as_text=True)

    assert "battery_pack_architecture.pdf" in body


def test_revision_action_opens_attachments(db_session, admin_client):
    revision_id = _revision_id(db_session)

    response = admin_client.post(
        f"/revisionmodelview/action/view_attachments/{revision_id}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert f"/revision/{revision_id}/attachments" in response.headers["Location"]


def test_remove_file(db_session, admin_client):
    revision_id = _revision_id(db_session)
    _upload(admin_client, revision_id, "remove-me.txt", b"bye")
    db_session.expire_all()
    managed = db_session.query(ManagedFile).filter_by(file_name="remove-me.txt").one()
    managed_id = managed.id

    response = admin_client.post(
        f"/file/{managed_id}/remove", follow_redirects=True
    )

    assert b"File removed" in response.data
    db_session.expire_all()
    assert db_session.query(ManagedFile).filter_by(id=managed_id).one_or_none() is None


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_viewer_denied_attachments(db_session, viewer_client):
    revision_id = _revision_id(db_session)
    managed = db_session.query(ManagedFile).first()

    assert (
        viewer_client.get(f"/revision/{revision_id}/attach").status_code == 403
    )
    assert (
        viewer_client.get(f"/revision/{revision_id}/attachments").status_code
        == 403
    )
    assert viewer_client.get(f"/file/{managed.id}/download").status_code == 403