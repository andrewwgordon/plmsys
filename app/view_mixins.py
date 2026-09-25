"""Reusable Flask-AppBuilder ModelView mixins (Phase 2).

The mixins keep the views thin: they translate FAB actions into calls on the
Phase 1 services (`revisions`, `lifecycle`) and own the transaction, flash and
redirect handling. Business rules stay in ``app/services/``.
"""

from flask import flash, redirect
from flask_appbuilder import action
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .services import ServiceError, lifecycle, revisions


def _normalise(items):
    """FAB passes a single model to *show* actions and a list to *list* actions."""
    if items is None:
        return []
    if isinstance(items, (list, tuple, set)):
        return [item for item in items if item is not None]
    return [items]


class RevisionActionMixin:
    """Shared transaction/flash/redirect handling for revision actions."""

    def _run_revision_action(self, items, operation, success):
        # Push the current URL so ``get_redirect()`` returns to the referring
        # page (FAB's page-history convention; cf. BaseCRUDView.get_redirect).
        self.update_redirect()
        items = _normalise(items)
        if not items:
            flash("No records selected.", "warning")
            return redirect(self.get_redirect())

        messages = []
        try:
            for item in items:
                result = operation(item)
                messages.append(success(result) if callable(success) else success)
        except ServiceError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except IntegrityError:
            # e.g. two concurrent "Create Revision" requests computing the same
            # label: the unique constraint fires before any ServiceError.
            db.session.rollback()
            flash(
                "The change conflicts with existing data "
                "(duplicate or concurrent update).",
                "danger",
            )
        else:
            db.session.commit()
            for message in messages:
                flash(message, "success")
        return redirect(self.get_redirect())


class CreateRevisionMixin(RevisionActionMixin):
    """Adds a ``Create Revision`` action to a BusinessObject ModelView.

    Revisions are always created through ``revisions.create_revision`` so the
    revision label, lineage, property copy and initial ``Draft`` state are
    recorded consistently.
    """

    @action(
        "create_revision",
        "Create Revision",
        "Create a new Draft revision for the selected object?",
        "fa-code-fork",
        single=True,
        multiple=False,
    )
    def create_revision_action(self, item):
        def operation(business_object):
            return revisions.create_revision(business_object)

        def success(revision):
            return (
                f"Created revision {revision.revision_id} for "
                f"{revision.business_object.object_number}."
            )

        return self._run_revision_action(item, operation, success)


class RevisionLifecycleMixin(RevisionActionMixin):
    """Revision-level lifecycle and current-revision actions."""

    @action(
        "set_current_revision",
        "Set Current Revision",
        "Make this the object's current revision?",
        "fa-check-circle",
        single=True,
        multiple=False,
    )
    def set_current_revision_action(self, item):
        def operation(revision):
            return revisions.revert_to_revision(revision.business_object, revision)

        def success(revision):
            return (
                f"{revision.business_object.object_number} now points at "
                f"revision {revision.revision_id}."
            )

        return self._run_revision_action(item, operation, success)

    def _transition(self, item, operation):
        def run(revision):
            # The lifecycle service returns the assigned ReleaseState; keep the
            # revision so the flash message can name it and its new state.
            operation(revision)
            return revision

        def success(revision):
            return (
                f"Revision {revision.revision_id} is now "
                f"{lifecycle.current_state_name(revision)}."
            )

        return self._run_revision_action(item, run, success)

    @action(
        "submit_for_review",
        "Submit for Review",
        None,
        "fa-paper-plane",
        single=True,
        multiple=False,
    )
    def submit_for_review_action(self, item):
        return self._transition(item, lifecycle.submit_for_review)

    @action(
        "approve_revision",
        "Approve",
        "Approve this revision?",
        "fa-thumbs-up",
        single=True,
        multiple=False,
    )
    def approve_revision_action(self, item):
        return self._transition(item, lifecycle.approve)

    @action(
        "release_revision",
        "Release",
        "Release this revision?",
        "fa-check",
        single=True,
        multiple=False,
    )
    def release_revision_action(self, item):
        return self._transition(item, lifecycle.release)

    @action(
        "obsolete_revision",
        "Obsolete",
        "Mark this revision obsolete?",
        "fa-ban",
        single=True,
        multiple=False,
    )
    def obsolete_revision_action(self, item):
        return self._transition(item, lifecycle.obsolete)


__all__ = ["CreateRevisionMixin", "RevisionLifecycleMixin"]
