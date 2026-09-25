"""Revision attachment pages (Phase 7).

A service-backed upload form, a read-only attachments list, and the
authenticated download/remove routes. Every write goes through
``services.datasets`` so extension, size, checksum and physical-file cleanup are
handled in one place; uploads are never served from the web-served static tree.
"""

import os

from flask import abort, flash, redirect, send_file, url_for
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access
from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from wtforms import FileField, StringField
from wtforms.validators import Optional

from ..extensions import db
from ..models import Dataset, ManagedFile, Revision
from ..services import ServiceError, datasets


def _conflict_flash():
    flash(
        "The change conflicts with existing data "
        "(duplicate or concurrent update).",
        "danger",
    )


def _load_revision(pk):
    revision = (
        db.session.query(Revision)
        .options(selectinload(Revision.datasets).selectinload(Dataset.files))
        .filter_by(id=pk)
        .one_or_none()
    )
    if revision is None or revision.business_object is None:
        abort(404)
    return revision


class AttachFileForm(FlaskForm):
    file = FileField("File")
    dataset_name = StringField("Dataset", validators=[Optional()])
    dataset_type = StringField("Type", validators=[Optional()])


class AttachFileView(BaseView):
    route_base = "/revision"
    default_view = "attach"
    method_permission_name = {"attach": "edit"}

    @expose("/<int:pk>/attach", methods=["GET", "POST"])
    @has_access
    def attach(self, pk):
        revision = _load_revision(pk)
        form = AttachFileForm()

        if form.validate_on_submit():
            try:
                datasets.attach_file(
                    revision,
                    form.file.data,
                    dataset_name=form.dataset_name.data,
                    dataset_type=form.dataset_type.data,
                )
            except ServiceError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except IntegrityError:
                db.session.rollback()
                _conflict_flash()
            else:
                db.session.commit()
                flash("File attached.", "success")
                return redirect(
                    url_for(
                        "RevisionAttachmentsView.attachments", pk=revision.id
                    )
                )

        return self.render_template(
            "attach_file.html", revision=revision, form=form
        )


class RevisionAttachmentsView(BaseView):
    route_base = "/revision"
    default_view = "attachments"
    method_permission_name = {"attachments": "show"}

    @expose("/<int:pk>/attachments", methods=["GET"])
    @has_access
    def attachments(self, pk):
        revision = _load_revision(pk)
        return self.render_template(
            "attachments.html", revision=revision
        )


class DownloadFileView(BaseView):
    route_base = "/file"
    default_view = "download"
    method_permission_name = {"download": "show"}

    @expose("/<int:pk>/download", methods=["GET"])
    @has_access
    def download(self, pk):
        managed_file = db.session.get(ManagedFile, pk)
        if managed_file is None or not managed_file.file:
            abort(404)
        path = datasets.file_path(managed_file)
        if not os.path.exists(path):
            abort(404)
        return send_file(
            path,
            download_name=managed_file.file_name,
            as_attachment=True,
            mimetype=managed_file.mime_type or "application/octet-stream",
        )


class RemoveFileView(BaseView):
    route_base = "/file"
    default_view = "remove"
    method_permission_name = {"remove": "delete"}

    @expose("/<int:pk>/remove", methods=["POST"])
    @has_access
    def remove(self, pk):
        managed_file = db.session.get(ManagedFile, pk)
        if managed_file is None:
            abort(404)
        revision_id = managed_file.dataset.revision_id
        try:
            datasets.delete_file(managed_file)
        except ServiceError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            db.session.commit()
            flash("File removed.", "success")
        return redirect(
            url_for("RevisionAttachmentsView.attachments", pk=revision_id)
        )


__all__ = [
    "AttachFileView",
    "DownloadFileView",
    "RemoveFileView",
    "RevisionAttachmentsView",
]