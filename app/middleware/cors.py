"""Middleware CORS: cho phép FE (khác origin) gọi API.

Origin được phép đọc từ config CORS_ORIGINS (phân tách bằng dấu phẩy).
Dùng "*" để cho phép mọi origin (chỉ nên dùng ở môi trường dev).
"""
from ..extensions import cors


def init_cors(app):
    raw = str(app.config.get("CORS_ORIGINS", "*")).strip()
    origins = "*" if raw == "*" else [o.strip() for o in raw.split(",") if o.strip()]

    cors.init_app(
        app,
        resources={r"/api/*": {"origins": origins}},
        supports_credentials=app.config.get("CORS_SUPPORTS_CREDENTIALS", True),
        expose_headers=["X-Request-ID"],
    )
