"""Traceability pages (Phase 4).

Relation forms (add relation, derive requirement), the revision relations
section and the read-only traceability matrix. All writes go through
``services.relationships`` (and ``services.revisions``/``services.properties``
for derive), so the service guards are never bypassed.
"""

from flask import abort, flash, redirect, url_for
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access
from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

from ..extensions import db
from ..models import BusinessObject, ObjectType, Relationship, Revision
from ..services import ServiceError, properties, relationships, revisions

# Offered by the generic Add Relation form.
_RELATION_TYPES = ("DEFINING", "ALLOCATED_TO", "VERIFIED_BY", "SATISFIED_BY")
# Columns shown by the matrix (all outbound from the requirement revision).
_MATRIX_TYPES = ("DEFINING", "ALLOCATED_TO", "VERIFIED_BY", "SATISFIED_BY")
# Allowed target object types per relationship type (typed traceability).
_TARGET_TYPES = {
    "DEFINING": {"Requirement"},
    "ALLOCATED_TO": {"ArchitectureElement", "Part", "SoftwareComponent"},
    "VERIFIED_BY": {"TestCase"},
    "SATISFIED_BY": {"Part", "Function", "SoftwareComponent", "ArchitectureElement"},
}
_ALLOWED_TARGET_TYPES = tuple(sorted(set().union(*_TARGET_TYPES.values())))


def _requirement_type():
    object_type = (
        db.session.query(ObjectType).filter_by(name="Requirement").one_or_none()
    )
    if object_type is None:
        abort(404)
    return object_type


def _selectable_objects(exclude_object_id):
    """Objects that are valid targets for at least one relationship type."""
    return (
        db.session.query(BusinessObject)
        .join(ObjectType, BusinessObject.object_type_id == ObjectType.id)
        .filter(BusinessObject.id != exclude_object_id)
        .filter(ObjectType.name.in_(_ALLOWED_TARGET_TYPES))
        .order_by(BusinessObject.object_number)
        .all()
    )


def _conflict_flash():
    flash(
        "The change conflicts with existing data "
        "(duplicate or concurrent update).",
        "danger",
    )


def _target_label(business_object):
    return (
        f"{business_object.object_number} - {business_object.name} "
        f"({business_object.object_type.name})"
    )


def _group_edges(edges):
    """Group ``[(relationship, neighbour), …]`` by relationship type name."""
    groups = {}
    for relationship, neighbour in edges:
        groups.setdefault(relationship.relationship_type.name, []).append(neighbour)
    return groups


class AddRelationForm(FlaskForm):
    relationship_type = SelectField("Relationship", choices=[])
    target = SelectField("Target", coerce=int, choices=[])


class DeriveRequirementForm(FlaskForm):
    object_number = StringField("Number", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])
    copy_properties = BooleanField(
        "Copy properties from the source revision", default=True
    )


def _build_add_relation_form(revision):
    form = AddRelationForm()
    form.relationship_type.choices = [
        (name, name) for name in _RELATION_TYPES
    ]
    form.target.choices = [
        (obj.id, _target_label(obj))
        for obj in _selectable_objects(revision.object_id)
    ]
    return form


class RelationFormView(BaseView):
    route_base = "/relation"
    default_view = "add"
    method_permission_name = {"add": "edit"}

    @expose("/<int:pk>/", methods=["GET", "POST"])
    @has_access
    def add(self, pk):
        revision = db.session.get(Revision, pk)
        if revision is None:
            abort(404)
        form = _build_add_relation_form(revision)

        if form.validate_on_submit():
            target = db.session.get(BusinessObject, form.target.data)
            target_revision = target.current_revision if target else None
            allowed = _TARGET_TYPES.get(form.relationship_type.data, set())
            target_type_name = target.object_type.name if target else None
            if target_revision is None:
                flash("The selected object has no current revision.", "danger")
            elif allowed and target_type_name not in allowed:
                flash(
                    f"{form.relationship_type.data} cannot target a "
                    f"{target_type_name}.",
                    "danger",
                )
            else:
                try:
                    relationships.create_relationship(
                        form.relationship_type.data, revision, target_revision
                    )
                except ServiceError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
                except IntegrityError:
                    db.session.rollback()
                    _conflict_flash()
                else:
                    db.session.commit()
                    flash("Relationship created.", "success")
                    return redirect(
                        url_for("RevisionRelationsView.relations", pk=pk)
                    )

        return self.render_template(
            "relation_form.html", revision=revision, form=form
        )


class DeriveRequirementView(BaseView):
    route_base = "/relation"
    default_view = "derive"
    method_permission_name = {"derive": "edit"}

    @expose("/<int:pk>/derive", methods=["GET", "POST"])
    @has_access
    def derive(self, pk):
        source = db.session.get(Revision, pk)
        if (
            source is None
            or source.business_object is None
            or source.business_object.object_type.name != "Requirement"
        ):
            abort(404)
        form = DeriveRequirementForm()

        if form.validate_on_submit():
            object_number = form.object_number.data.strip()
            try:
                if (
                    db.session.query(BusinessObject)
                    .filter_by(object_number=object_number)
                    .count()
                ):
                    raise ServiceError(
                        f"Object number {object_number!r} already exists"
                    )
                business_object = BusinessObject(
                    object_type=_requirement_type(),
                    object_number=object_number,
                    name=form.name.data,
                    description=form.description.data or None,
                )
                db.session.add(business_object)
                db.session.flush()
                new_revision = revisions.create_revision(
                    business_object,
                    title=form.name.data,
                    description=form.description.data,
                    session=db.session,
                )
                if form.copy_properties.data:
                    properties.copy_properties(source, new_revision, session=db.session)
                relationships.create_relationship(
                    "DEFINING", source, new_revision, session=db.session
                )
            except ServiceError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except IntegrityError:
                db.session.rollback()
                _conflict_flash()
            else:
                db.session.commit()
                flash(
                    f"Requirement {object_number} created and derived.",
                    "success",
                )
                return redirect(
                    url_for("RevisionRelationsView.relations", pk=pk)
                )

        return self.render_template(
            "derive_requirement.html", revision=source, form=form
        )


class RevisionRelationsView(BaseView):
    route_base = "/revision"
    default_view = "relations"
    method_permission_name = {"relations": "show"}

    @expose("/<int:pk>/relations", methods=["GET"])
    @has_access
    def relations(self, pk):
        revision = db.session.get(Revision, pk)
        if revision is None:
            abort(404)
        return self.render_template(
            "revision_relations.html",
            revision=revision,
            outbound=_group_edges(relationships.neighbours(revision, "out")),
            inbound=_group_edges(relationships.neighbours(revision, "in")),
        )


class TraceabilityMatrixView(BaseView):
    route_base = "/traceability"
    default_view = "matrix"
    method_permission_name = {"matrix": "list"}

    @expose("/", methods=["GET"])
    @has_access
    def matrix(self):
        requirement_type = _requirement_type()
        revisions = (
            db.session.query(Revision)
            .join(BusinessObject, Revision.object_id == BusinessObject.id)
            .filter(BusinessObject.object_type_id == requirement_type.id)
            .filter(BusinessObject.current_revision_id == Revision.id)
            .options(selectinload(Revision.business_object))
            .order_by(BusinessObject.object_number, Revision.sequence_no)
            .all()
        )

        # One bulk query for every outbound edge of the row set (no per-row N+1).
        by_primary = {}
        revision_ids = [revision.id for revision in revisions]
        if revision_ids:
            edges = (
                db.session.query(Relationship)
                .filter(Relationship.primary_revision_id.in_(revision_ids))
                .options(
                    joinedload(Relationship.relationship_type),
                    joinedload(Relationship.secondary_revision).joinedload(
                        Revision.business_object
                    ),
                )
                .all()
            )
            for relationship in edges:
                by_primary.setdefault(relationship.primary_revision_id, {}).setdefault(
                    relationship.relationship_type.name, []
                ).append(relationship.secondary_revision)

        rows = []
        for revision in revisions:
            cells = {
                type_name: by_primary.get(revision.id, {}).get(type_name, [])
                for type_name in _MATRIX_TYPES
            }
            verified = bool(cells["VERIFIED_BY"])
            implemented = bool(cells["ALLOCATED_TO"] or cells["SATISFIED_BY"])
            rows.append(
                {
                    "revision": revision,
                    "cells": cells,
                    "gap": not verified and not implemented,
                }
            )

        return self.render_template(
            "traceability_matrix.html", types=_MATRIX_TYPES, rows=rows
        )


__all__ = [
    "DeriveRequirementView",
    "RelationFormView",
    "RevisionRelationsView",
    "TraceabilityMatrixView",
]
