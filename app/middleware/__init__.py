"""Gói middleware: CORS, rate limit, logging, validation.

`register_middlewares(app)` gắn các middleware cấp ứng dụng (logging, CORS,
rate limit). Validation áp theo từng route qua decorator `validate_body` /
`validate_query`.
"""
from .auth import current_user, require_auth
from .cors import init_cors
from .logging import init_logging
from .rate_limit import init_rate_limit, rate_limit
from .validation import (
    Field,
    validate_body,
    validate_query,
    validated,
    validated_query,
)

__all__ = [
    "register_middlewares",
    "rate_limit",
    "require_auth",
    "current_user",
    "Field",
    "validate_body",
    "validate_query",
    "validated",
    "validated_query",
]


def register_middlewares(app):
    # Logging trước để bắt được mọi request; CORS & rate limit sau đó.
    init_logging(app)
    init_cors(app)
    init_rate_limit(app)
