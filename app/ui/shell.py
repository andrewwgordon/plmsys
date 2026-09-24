"""UI-0 application shell: the Home page.

The Home page is the landing surface described in ``docs/ui_plan.md`` §7.1. It
provides KPI tiles, quick-entry tiles and a minimal object lookup that will be
superseded by the full Global Search view (UI-2, Phase 11).
"""

from flask import request
from flask_appbuilder import IndexView, expose
from sqlalchemy import func, or_

from ..extensions import db
from ..models import (
    Baseline,
    BusinessObject,
    ObjectType,
    Revision,
    WorkflowTask,
)


def _scalar(query, default=0):
    try:
        value = query.scalar()
        return int(value) if value is not None else default
    except Exception:
        return default


class PLMSysIndexView(IndexView):
    """Personal Home page for PLMSys."""

    index_template = "index.html"

    @expose("/")
    def index(self):
        self.update_redirect()

        query_text = (request.args.get("q") or "").strip()
        results = []
        if query_text:
            like = f"%{query_text}%"
            results = (
                db.session.query(BusinessObject)
                .filter(
                    or_(
                        BusinessObject.object_number.ilike(like),
                        BusinessObject.name.ilike(like),
                    )
                )
                .order_by(BusinessObject.object_number)
                .limit(50)
                .all()
            )

        counts = {
            "objects": _scalar(db.session.query(func.count(BusinessObject.id))),
            "revisions": _scalar(db.session.query(func.count(Revision.id))),
            "requirements": _scalar(
                db.session.query(func.count(BusinessObject.id))
                .join(BusinessObject.object_type)
                .filter(ObjectType.name == "Requirement")
            ),
            "baselines": _scalar(db.session.query(func.count(Baseline.id))),
            "open_tasks": _scalar(
                db.session.query(func.count(WorkflowTask.id)).filter(
                    WorkflowTask.task_state != "Done"
                )
            ),
        }

        return self.render_template(
            "index.html",
            appbuilder=self.appbuilder,
            counts=counts,
            query_text=query_text,
            results=results,
        )
