"""Middleware giới hạn tần suất (rate limit) bằng thuật toán Token Bucket.

- Áp giới hạn mặc định (RATELIMIT_CAPACITY / RATELIMIT_REFILL_RATE) cho mọi endpoint,
  tách riêng theo từng (IP client + endpoint).
- Siết/nới riêng từng route bằng decorator:
      @rate_limit(capacity=10, refill_rate=10/60)   # burst 10, hồi 10 req/phút
- Khi hết token: trả response chuẩn hóa (status 429) với message đã dịch,
  kèm `data.retry_after` (giây) và header Retry-After.
- Mỗi response bổ sung header X-RateLimit-Limit / X-RateLimit-Remaining.
"""
from flask import current_app, g, request

from ..common.response import error_response
from ..i18n import translate
from .token_bucket import TokenBucketLimiter

_limiter = TokenBucketLimiter()
_RULE_ATTR = "_rate_limit_rule"


def rate_limit(capacity, refill_rate):
    """Đặt giới hạn token bucket riêng cho một route.

    capacity:    số token tối đa (số request burst cho phép).
    refill_rate: tốc độ hồi token (token/giây).
    """

    def decorator(fn):
        setattr(fn, _RULE_ATTR, (float(capacity), float(refill_rate)))
        return fn

    return decorator


def _client_ip():
    # Ưu tiên X-Forwarded-For khi chạy sau proxy/load balancer.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "anonymous"


def init_rate_limit(app):
    enabled = app.config.get("RATELIMIT_ENABLED", True)
    default_capacity = float(app.config.get("RATELIMIT_CAPACITY", 120))
    default_refill = float(app.config.get("RATELIMIT_REFILL_RATE", 2.0))

    @app.before_request
    def _enforce_rate_limit():
        if not enabled or request.endpoint is None:
            return None

        view = app.view_functions.get(request.endpoint)
        capacity, refill_rate = getattr(
            view, _RULE_ATTR, (default_capacity, default_refill)
        )

        key = f"{_client_ip()}:{request.endpoint}"
        allowed, remaining, retry_after = _limiter.hit(key, capacity, refill_rate)

        # Lưu lại để after_request gắn header thông tin giới hạn.
        g.rate_limit = (int(capacity), remaining)

        if not allowed:
            body, status = error_response(
                translate("errors.rate_limited"),
                status_code=429,
                data={"retry_after": round(retry_after, 1) if retry_after else None},
            )
            response = current_app.make_response((body, status))
            if retry_after:
                response.headers["Retry-After"] = str(int(retry_after) + 1)
            response.headers["X-RateLimit-Limit"] = str(int(capacity))
            response.headers["X-RateLimit-Remaining"] = "0"
            return response
        return None

    @app.after_request
    def _set_rate_limit_headers(response):
        info = getattr(g, "rate_limit", None)
        if info is not None:
            limit, remaining = info
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
