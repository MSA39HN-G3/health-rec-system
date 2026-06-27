"""Danh sách token đã bị thu hồi (blacklist).

Khi logout, `jti` của token được lưu vào đây kèm thời điểm token hết hạn.
Mỗi request có xác thực sẽ kiểm tra `jti`: nếu nằm trong blacklist -> từ chối.
Bản ghi quá hạn (token đã tự hết hạn) có thể dọn định kỳ để tránh phình bảng.
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class TokenBlacklist(db.Model):
    __tablename__ = "token_blacklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
