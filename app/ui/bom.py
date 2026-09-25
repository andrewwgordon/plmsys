"""BOM pages (Phase 5).

The read-only structure explorer, the add-occurrence and link-requirement
forms, and the requirement-coverage report. All writes go through
``services.bom``.
"""

import math

from flask import abort, flash, redirect, url_for
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access
from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from wtforms import FloatField, SelectField, StringField
from wtforms.validators import DataRequired, ValidationError

from ..extensions import db
from ..models import BOMOccurrence, BusinessObject, ObjectType, OccurrenceTrace, Revision
from ..services import ServiceError, bom


def _conflict_flash():
    flash(
        "The change conflicts with existing data "
        "(duplicate or concurrent update).",
        "danger",
    )


def _part_objects(exclude_object_id):
    return (
        db.session.query(BusinessObject)
        .join(ObjectType, BusinessObject.object_type_id == ObjectType.id)
        .filter(ObjectType.name == "Part")
        .filter(BusinessObject.id != exclude_object_id)
        .order_by(BusinessObject.object_number)
        .all()
    )


def _requirement_objects():
    return (
        db.session.query(BusinessObject)
        .join(ObjectType, BusinessObject.object_type_id == ObjectType.id)
        .filter(ObjectType.name == "Requirement")
        .order_by(BusinessObject.object_number)
        .all()
    )


def _label(business_object):
    return f"{business_object.object_number} - {business_object.name}"


def _is_part(revision) -> bool:
    business_object = revision.business_object
    return (
        business_object is not None
        and business_object.object_type is not None
        and business_object.object_type.name == "Part"
    )


def _finite_positive(form, field):
    if field.data is None or not math.isfinite(field.data) or field.data <= 0:
        raise ValidationError(
            "Quantity must be a finite number greater than zero."
        )


class AddOccurrenceForm(FlaskForm):
    child = SelectField("Child part", coerce=int, choices=[])
    find_number = StringField("Find number", validators=[DataRequired()])
    quantity = FloatField(
        "Quantity", default=1.0, validators=[DataRequired(), _finite_positive]
    )


class LinkRequirementForm(FlaskForm):
    requirement = SelectField("Requirement", coerce=int, choices=[])


class DeleteForm(FlaskForm):
    """Empty form so the delete action is CSRF-protected."""


def _trace_map(session, occurrence_ids):
    traces = {}
    if occurrence_ids:
        rows = (
            session.query(OccurrenceTrace)
            .filter(OccurrenceTrace.bom_occurrence_id.in_(occurrence_ids))
            .options(
                joinedload(OccurrenceTrace.requirement_revision).joinedload(
                    Revision.business_object
                )
            )
            .all()
        )
        for trace in rows:
            traces.setdefault(trace.bom_occurrence_id, []).append(
                trace.requirement_revision
            )
    return traces


class BomTreeView(BaseView):
    route_base = "/bom"
    default_view = "tree"
    method_permission_name = {"tree": "show"}

    @expose("/<int:pk>/", methods=["GET"])
    @has_access
    def tree(self, pk):
        revision = db.session.get(Revision, pk)
        if revision is None:
            abort(404)
        if not _is_part(revision):
            flash("BOM is only available for Part revisions.", "danger")
            return redirect(url_for("RevisionModelView.show", pk=pk))

        rows = bom.explode(revision)
        rollup = bom.bom_rollup(revision, rows=rows)
        traces = _trace_map(db.session, [row["occurrence"].id for row in rows])
        for row in rows:
            row["traces"] = traces.get(row["occurrence"].id, [])
            row["rollup"] = rollup.get(row["child_revision"].id)

        return self.render_template(
            "bom_tree.html",
            revision=revision,
            rows=rows,
            used_in=bom.where_used(revision),
            delete_form=DeleteForm(),
        )


class AddOccurrenceView(BaseView):
    route_base = "/bom"
    default_view = "add"
    method_permission_name = {"add": "edit"}

    @expose("/<int:pk>/add", methods=["GET", "POST"])
    @has_access
    def add(self, pk):
        parent = db.session.get(Revision, pk)
        if parent is None:
            abort(404)
        if not _is_part(parent):
            flash("BOM is only available for Part revisions.", "danger")
            return redirect(url_for("RevisionModelView.show", pk=pk))

        form = AddOccurrenceForm()
        form.child.choices = [
            (obj.id, _label(obj)) for obj in _part_objects(parent.object_id)
        ]

        if form.validate_on_submit():
            child = db.session.get(BusinessObject, form.child.data)
            child_revision = child.current_revision if child else None
            if child_revision is None:
                flash("The selected part has no current revision.", "danger")
            else:
                try:
                    bom.add_occurrence(
                        parent,
                        child_revision,
                        form.find_number.data,
                        form.quantity.data,
                    )
                except ServiceError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
                except IntegrityError:
                    db.session.rollback()
                    _conflict_flash()
                else:
                    db.session.commit()
                    flash("BOM line added.", "success")
                    return redirect(url_for("BomTreeView.tree", pk=pk))

        return self.render_template(
            "add_occurrence.html", revision=parent, form=form
        )


class LinkRequirementView(BaseView):
    route_base = "/bom"
    default_view = "link"
    method_permission_name = {"link": "edit"}

    @expose("/occurrence/<int:pk>/trace", methods=["GET", "POST"])
    @has_access
    def link(self, pk):
        occurrence = db.session.get(BOMOccurrence, pk)
        if occurrence is None:
            abort(404)
        parent_id = occurrence.parent_revision_id
        form = LinkRequirementForm()
        form.requirement.choices = [
            (obj.id, _label(obj)) for obj in _requirement_objects()
        ]

        if form.validate_on_submit():
            requirement = db.session.get(BusinessObject, form.requirement.data)
            requirement_revision = (
                requirement.current_revision if requirement else None
            )
            if requirement_revision is None:
                flash(
                    "The selected requirement has no current revision.", "danger"
                )
            else:
                try:
                    bom.link_requirement(occurrence, requirement_revision)
                except ServiceError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
                except IntegrityError:
                    db.session.rollback()
                    _conflict_flash()
                else:
                    db.session.commit()
                    flash("Requirement traced to the BOM line.", "success")
                    return redirect(
                        url_for("BomTreeView.tree", pk=parent_id)
                    )

        return self.render_template(
            "link_requirement.html", occurrence=occurrence, form=form
        )


class BomCoverageView(BaseView):
    route_base = "/bom-coverage"
    default_view = "coverage"
    method_permission_name = {"coverage": "list"}

    @expose("/", methods=["GET"])
    @has_access
    def coverage(self):
        return self.render_template(
            "bom_coverage.html", occurrences=bom.uncovered_occurrences()
        )


class RemoveOccurrenceView(BaseView):
    route_base = "/bom"
    default_view = "remove"
    method_permission_name = {"remove": "edit"}

    @expose("/occurrence/<int:pk>/delete", methods=["POST"])
    @has_access
    def remove(self, pk):
        occurrence = db.session.get(BOMOccurrence, pk)
        if occurrence is None:
            abort(404)
        parent_id = occurrence.parent_revision_id
        form = DeleteForm()
        if form.validate_on_submit():
            try:
                bom.remove_occurrence(occurrence)
            except IntegrityError:
                db.session.rollback()
                _conflict_flash()
            else:
                db.session.commit()
                flash("BOM line removed.", "success")
        return redirect(url_for("BomTreeView.tree", pk=parent_id))


__all__ = [
    "AddOccurrenceView",
    "BomCoverageView",
    "BomTreeView",
    "LinkRequirementView",
    "RemoveOccurrenceView",
]
