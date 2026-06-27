"""Service xử lý đăng nhập bằng Google theo luồng OAuth2 Authorization Code.

Luồng tổng quát:
    1. BE sinh URL đăng nhập Google -> FE redirect người dùng tới đó.
    2. Người dùng đồng ý -> Google redirect về GOOGLE_REDIRECT_URI kèm `code`.
    3. FE gửi `code` lên BE -> BE đổi code lấy token tại Google (xác thực code),
       rồi verify `id_token` (kiểm tra chữ ký + audience) để lấy thông tin user.

Tài liệu: https://developers.google.com/identity/protocols/oauth2/web-server
"""
import logging
import secrets
from urllib.parse import urlencode

import requests
from flask import current_app
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from ..errors import AppException, UnauthorizedException

logger = logging.getLogger(__name__)

# Các endpoint công khai của Google.
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

_HTTP_TIMEOUT = 10  # giây
# Cho phép lệch đồng hồ nhỏ giữa server và Google (giây).
_CLOCK_SKEW = 10


def _require_config():
    """Đảm bảo đã cấu hình client id/secret; nếu thiếu là lỗi cấu hình phía server (500)."""
    cfg = current_app.config
    if not cfg.get("GOOGLE_CLIENT_ID") or not cfg.get("GOOGLE_CLIENT_SECRET"):
        raise AppException("errors.google_not_configured", status_code=500)
    return cfg


def generate_state():
    """Sinh chuỗi `state` ngẫu nhiên để FE lưu lại và chống tấn công CSRF."""
    return secrets.token_urlsafe(32)


def build_authorization_url(state):
    """Tạo URL để FE redirect người dùng sang trang đăng nhập của Google."""
    cfg = _require_config()
    params = {
        "client_id": cfg["GOOGLE_CLIENT_ID"],
        "redirect_uri": cfg["GOOGLE_REDIRECT_URI"],
        "response_type": "code",
        "scope": cfg["GOOGLE_OAUTH_SCOPES"],
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URI}?{urlencode(params)}"


def exchange_code_for_tokens(code):
    """Đổi authorization_code lấy token tại Google. Đây chính là bước Google xác thực code."""
    cfg = _require_config()
    payload = {
        "code": code,
        "client_id": cfg["GOOGLE_CLIENT_ID"],
        "client_secret": cfg["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": cfg["GOOGLE_REDIRECT_URI"],
        "grant_type": "authorization_code",
    }
    try:
        resp = requests.post(GOOGLE_TOKEN_URI, data=payload, timeout=_HTTP_TIMEOUT)
    except requests.RequestException:
        # Không gọi được Google (timeout, mất mạng...).
        raise AppException("errors.google_unreachable", status_code=502)

    if resp.status_code != 200:
        # code sai/hết hạn, redirect_uri không khớp, client secret sai...
        raise UnauthorizedException(
            "errors.google_code_invalid", details=_safe_google_error(resp)
        )
    return resp.json()


def verify_id_token(id_token_str):
    """Verify id_token (JWT) của Google: kiểm tra chữ ký, issuer và audience (client id).

    Trả về dict claims: sub, email, email_verified, name, picture, ...
    """
    cfg = _require_config()
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            cfg["GOOGLE_CLIENT_ID"],
            clock_skew_in_seconds=_CLOCK_SKEW,
        )
    except ValueError as exc:
        # Token không hợp lệ / sai audience / hết hạn / lệch đồng hồ.
        # Log lý do thật để dễ chẩn đoán (vd "Token expired", "Token used too early").
        logger.warning("Google id_token verification failed: %s", exc)
        raise UnauthorizedException(
            "errors.google_token_invalid", details={"reason": str(exc)}
        )
    return claims


def _safe_google_error(resp):
    """Trích thông điệp lỗi từ Google (không lộ dữ liệu nhạy cảm) để đưa vào details."""
    try:
        body = resp.json()
        return {"reason": body.get("error"), "description": body.get("error_description")}
    except ValueError:
        return None
