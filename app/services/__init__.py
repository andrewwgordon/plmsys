"""Domain services for PLMSys.

This package holds the business rules that used to live in views/models:
revision creation, metadata-driven property coercion, lifecycle transitions and
relationship traversal. Services are HTTP-free and raise :class:`ServiceError`
for expected validation failures so callers can turn them into flash messages.

See ``docs/plan.md`` Phase 1.
"""


class ServiceError(Exception):
    """Raised when a domain service rejects an operation.

    Expected, user-facing validation failures should raise this (rather than a
    generic ``ValueError``/SQLAlchemy error) so views can present a clean
    message.
    """


__all__ = ["ServiceError"]
