"""Phát và giải mã JWT phiên đăng nhập do hệ thống tự cấp.

Mỗi token mang `jti` (id duy nhất) để có thể thu hồi (đưa vào blacklist khi logout).
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app


def _now():
    return datetime.now(timezone.utc)


def issue_access_token(user):
    """Cấp access token cho user. Trả về (token_str, jti, expires_at)."""
    cfg = current_app.config
    now = _now()
    expires_at = now + timedelta(seconds=cfg["JWT_EXPIRES"])
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user.id),
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, cfg["JWT_SECRET"], algorithm=cfg["JWT_ALGORITHM"])
    return token, jti, expires_at


def decode_token(token):
    """Giải mã & xác thực token. Ném jwt.ExpiredSignatureError / jwt.InvalidTokenError."""
    cfg = current_app.config
    return jwt.decode(token, cfg["JWT_SECRET"], algorithms=[cfg["JWT_ALGORITHM"]])
