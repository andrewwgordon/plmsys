"""Custom property pages (Phase 3).

``RevisionPropertiesView`` renders and saves a revision's metadata-driven
properties — one WTForms field per ``PropertyDefinition`` (``FieldList`` for
multi-valued definitions). ``PropertyMatrixView`` is the read-only
rows-by-definitions report. Both delegate all writes to
``app.services.properties``.
"""

from flask import abort, flash, redirect, request, url_for
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access
from flask_wtf import FlaskForm
from sqlalchemy.orm import selectinload
from wtforms import (
    DateField,
    FieldList,
    FloatField,
    IntegerField,
    StringField,
)

from ..extensions import db
from ..models import (
    BusinessObject,
    ObjectType,
    PropertyDataType,
    PropertyDefinition,
    PropertyValue,
    Revision,
)
from ..services import ServiceError, properties

_FIELD_CLASSES = {
    PropertyDataType.STRING: StringField,
    PropertyDataType.INTEGER: IntegerField,
    PropertyDataType.FLOAT: FloatField,
    PropertyDataType.DATE: DateField,
}


def _field_name(definition) -> str:
    # Prefix avoids collisions with WTForms' own attributes (data/errors/meta).
    return f"prop_{definition.name}"


def _definitions_for(object_type):
    return (
        db.session.query(PropertyDefinition)
        .filter_by(object_type_id=object_type.id)
        .order_by(PropertyDefinition.name)
        .all()
    )


def _min_entries(revision, definitions):
    existing = properties.get_properties(revision)
    return {
        _field_name(definition): max(len(existing.get(definition.name) or []), 1)
        for definition in definitions
        if definition.multi_value
    }


def _build_form_class(definitions, min_entries=None):
    min_entries = min_entries or {}
    fields = {}
    for definition in definitions:
        field_class = _FIELD_CLASSES[properties.data_type_of(definition)]
        name = _field_name(definition)
        if definition.multi_value:
            fields[name] = FieldList(
                field_class(), min_entries=min_entries.get(name, 1)
            )
        else:
            fields[name] = field_class()
    return type("RevisionPropertiesForm", (FlaskForm,), fields)


def _populate(form, revision, definitions):
    values = properties.get_properties(revision)
    for definition in definitions:
        field = form[_field_name(definition)]
        value = values.get(definition.name)
        if definition.multi_value:
            for index, entry in enumerate(field.entries):
                if index < len(value or []):
                    entry.data = value[index]
        else:
            field.data = value


def _save(revision, definitions, form):
    for definition in definitions:
        field = form[_field_name(definition)]
        if definition.multi_value:
            values = [
                entry.data
                for entry in field.entries
                if entry.data not in (None, "")
            ]
            if definition.mandatory and not values:
                raise ServiceError(f"Property {definition.name!r} is mandatory")
            for sequence_no, value in enumerate(values, start=1):
                properties.set_property(
                    revision, definition, value, sequence_no=sequence_no
                )
            existing = {
                pv.sequence_no
                for pv in revision.property_values
                if pv.property_definition_id == definition.id
            }
            for sequence_no in sorted(existing):
                if sequence_no > len(values):
                    properties.delete_property(revision, definition, sequence_no)
        else:
            properties.set_property(revision, definition, field.data)

    missing = properties.validate_required(revision)
    if missing:
        raise ServiceError("Missing mandatory properties: " + ", ".join(missing))


class RevisionPropertiesView(BaseView):
    route_base = "/revision"
    default_view = "properties"
    method_permission_name = {"properties": "edit"}

    @expose("/<int:pk>/properties", methods=["GET", "POST"])
    @has_access
    def properties(self, pk):
        revision = db.session.get(Revision, pk)
        if revision is None or revision.business_object is None:
            abort(404)

        definitions = _definitions_for(revision.business_object.object_type)
        form_class = _build_form_class(
            definitions, min_entries=_min_entries(revision, definitions)
        )
        form = form_class(
            formdata=request.form if request.method == "POST" else None
        )

        if request.method == "GET":
            _populate(form, revision, definitions)
        else:
            add_field = request.form.get("add_field")
            if add_field and add_field in form:
                # "Add value" was pressed for a multi-valued field: extend the
                # FieldList and re-render rather than saving.
                form[add_field].append_entry()
            elif form.validate():
                try:
                    _save(revision, definitions, form)
                except ServiceError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
                else:
                    db.session.commit()
                    flash("Properties saved.", "success")
                    return redirect(
                        url_for("RevisionPropertiesView.properties", pk=pk)
                    )
            else:
                flash("Please correct the errors below.", "danger")

        return self.render_template(
            "revision_properties.html",
            revision=revision,
            definitions=definitions,
            form=form,
        )


class PropertyMatrixView(BaseView):
    route_base = "/property-matrix"
    default_view = "matrix"
    method_permission_name = {"matrix": "list"}

    @expose("/", methods=["GET"])
    @has_access
    def matrix(self):
        object_types = db.session.query(ObjectType).order_by(ObjectType.name).all()
        type_name = request.args.get("object_type")
        if not type_name:
            type_name = (
                "Requirement"
                if any(o.name == "Requirement" for o in object_types)
                else (object_types[0].name if object_types else "Requirement")
            )

        definitions = (
            db.session.query(PropertyDefinition)
            .join(ObjectType, PropertyDefinition.object_type_id == ObjectType.id)
            .filter(ObjectType.name == type_name)
            .order_by(PropertyDefinition.name)
            .all()
        )
        selected_names = request.args.getlist("properties") or [
            definition.name for definition in definitions
        ]
        selected_definitions = [
            definition
            for definition in definitions
            if definition.name in selected_names
        ]

        revisions = (
            db.session.query(Revision)
            .join(BusinessObject, Revision.object_id == BusinessObject.id)
            .join(ObjectType, BusinessObject.object_type_id == ObjectType.id)
            .filter(ObjectType.name == type_name)
            .options(
                selectinload(Revision.property_values).selectinload(
                    PropertyValue.property_definition
                )
            )
            .order_by(BusinessObject.object_number, Revision.sequence_no)
            .all()
        )

        return self.render_template(
            "property_matrix.html",
            object_types=object_types,
            type_name=type_name,
            definitions=definitions,
            selected_names=selected_names,
            selected_definitions=selected_definitions,
            rows=properties.matrix(revisions, selected_definitions),
        )


__all__ = ["PropertyMatrixView", "RevisionPropertiesView"]
