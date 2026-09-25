"""Configuration pages (Phase 6).

Baseline creation (context-scoped), baseline detail grouped by object type,
a baseline compare page, and the session-based configuration-context selector.
All writes go through ``services.configuration``.
"""

from flask import abort, flash, g, redirect, request, session, url_for
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access
from flask_wtf import FlaskForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

from ..extensions import db
from ..models import (
    Baseline,
    BaselineMember,
    BusinessObject,
    ConfigurationContext,
    Revision,
)
from ..services import ServiceError, configuration


def _username():
    user = getattr(g, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return getattr(user, "username", None)
    return None


def _conflict_flash():
    flash(
        "The change conflicts with existing data "
        "(duplicate or concurrent update).",
        "danger",
    )


def active_context(contexts=None):
    """Return the session-selected configuration context, if any."""
    context_id = session.get("plmsys_context_id")
    if context_id is None:
        return None
    if contexts is None:
        contexts = db.session.query(ConfigurationContext).all()
    return next(
        (context for context in contexts if context.id == context_id), None
    )


class BaselineForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])


class CreateBaselineView(BaseView):
    route_base = "/configuration"
    default_view = "create_baseline"
    method_permission_name = {"create_baseline": "edit"}

    @expose("/<int:context_id>/baseline/new", methods=["GET", "POST"])
    @has_access
    def create_baseline(self, context_id):
        context = db.session.get(ConfigurationContext, context_id)
        if context is None:
            abort(404)
        form = BaselineForm()

        if form.validate_on_submit():
            try:
                baseline = configuration.create_baseline(
                    context,
                    form.name.data,
                    created_by=_username(),
                    description=form.description.data,
                )
            except ServiceError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
            except IntegrityError:
                db.session.rollback()
                _conflict_flash()
            else:
                db.session.commit()
                flash("Baseline created.", "success")
                return redirect(
                    url_for("BaselineDetailView.detail", pk=baseline.id)
                )

        return self.render_template(
            "create_baseline.html", context=context, form=form
        )


class BaselineDetailView(BaseView):
    route_base = "/baseline"
    default_view = "detail"
    method_permission_name = {"detail": "show"}

    @expose("/<int:pk>/", methods=["GET"])
    @has_access
    def detail(self, pk):
        baseline = db.session.get(Baseline, pk)
        if baseline is None:
            abort(404)

        members = (
            db.session.query(BaselineMember)
            .filter_by(baseline_id=baseline.id)
            .options(
                joinedload(BaselineMember.revision)
                .joinedload(Revision.business_object)
                .joinedload(BusinessObject.object_type)
            )
            .all()
        )
        groups = {}
        for member in sorted(
            members,
            key=lambda member: (
                member.revision.business_object.object_type.name,
                member.revision.business_object.object_number,
                member.revision.sequence_no or 0,
            ),
        ):
            revision = member.revision
            type_name = revision.business_object.object_type.name
            groups.setdefault(type_name, []).append(revision)

        return self.render_template(
            "baseline_detail.html", baseline=baseline, groups=groups
        )


class BaselineCompareView(BaseView):
    route_base = "/baseline"
    default_view = "compare"
    method_permission_name = {"compare": "list"}

    @expose("/compare", methods=["GET"])
    @has_access
    def compare(self):
        baselines = db.session.query(Baseline).order_by(Baseline.name).all()
        a_id = request.args.get("a", type=int)
        b_id = request.args.get("b", type=int)
        baseline_a = db.session.get(Baseline, a_id) if a_id else None
        baseline_b = db.session.get(Baseline, b_id) if b_id else None
        result = (
            configuration.compare_baselines(baseline_a, baseline_b)
            if baseline_a and baseline_b
            else None
        )
        return self.render_template(
            "baseline_compare.html",
            baselines=baselines,
            baseline_a=baseline_a,
            baseline_b=baseline_b,
            result=result,
        )


class SetContextView(BaseView):
    """Session-only configuration-context selector (persistence deferred).

    Available to any authenticated user: it only stores the selected context id
    in the session, so it does not need a FAB permission. Anonymous requests are
    rejected. The persisted ``UserPreference`` form arrives with UI-3.
    """

    route_base = "/context"
    default_view = "set_context"

    @expose("/set", methods=["POST"])
    def set_context(self):
        user = getattr(g, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            abort(401)
        context_id = request.form.get("context_id", type=int)
        if context_id:
            session["plmsys_context_id"] = context_id
        else:
            session.pop("plmsys_context_id", None)
        target = request.form.get("next") or "/"
        # Only allow same-site absolute paths: reject absolute URLs and
        # protocol-relative ones (``//evil.com``) to avoid an open redirect.
        if (
            not target.startswith("/")
            or target.startswith("//")
            or "\\" in target
        ):
            target = "/"
        return redirect(target)


__all__ = [
    "BaselineCompareView",
    "BaselineDetailView",
    "CreateBaselineView",
    "SetContextView",
    "active_context",
]
