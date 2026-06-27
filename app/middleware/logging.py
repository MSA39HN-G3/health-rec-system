"""Middleware ghi log: cấu hình logger gốc + log mỗi request HTTP.

- Cấu hình format/level cho toàn ứng dụng (đọc LOG_LEVEL từ config).
- Gắn cho mỗi request một `request_id` (đưa vào header phản hồi X-Request-ID)
  để dễ truy vết khi gặp sự cố.
- Ghi một dòng log khi request kết thúc: method, path, status, thời gian xử lý.
"""
import logging
import time
import uuid

from flask import g, request

logger = logging.getLogger("app.request")


def init_logging(app):
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)

    # Chỉ cấu hình handler một lần để tránh log bị nhân đôi khi reload.
    root = logging.getLogger()
    if not any(getattr(h, "_app_handler", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler._app_handler = True
        root.addHandler(handler)
    root.setLevel(level)

    skip_paths = {
        p.strip()
        for p in str(app.config.get("LOG_SKIP_PATHS", "")).split(",")
        if p.strip()
    }

    @app.before_request
    def _start_timer():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.request_start = time.perf_counter()

    @app.after_request
    def _log_request(response):
        # Trả request_id về client để đối chiếu log.
        request_id = getattr(g, "request_id", "-")
        response.headers["X-Request-ID"] = request_id

        if request.path in skip_paths:
            return response

        start = getattr(g, "request_start", None)
        duration_ms = round((time.perf_counter() - start) * 1000, 1) if start else -1
        logger.info(
            "%s %s -> %s (%sms) id=%s ip=%s",
            request.method,
            request.full_path.rstrip("?") if request.query_string else request.path,
            response.status_code,
            duration_ms,
            request_id,
            request.remote_addr,
        )
        return response
