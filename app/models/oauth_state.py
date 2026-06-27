"""Lưu `state` của luồng đăng nhập Google để chống CSRF.

- Khi FE gọi API lấy URL login, BE lưu `state` kèm thời điểm hết hạn.
- Khi FE gọi API callback, BE đối chiếu `state` nhận về với bản ghi đã lưu
  (còn hạn, chưa dùng) rồi đánh dấu đã dùng để không thể tái sử dụng.
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class OAuthState(db.Model):
    __tablename__ = "oauth_states"

    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(128), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))

    def is_usable(self, now=None):
        """State còn dùng được khi chưa bị dùng và chưa hết hạn."""
        now = now or _now()
        expires_at = self.expires_at
        # Một số backend (vd SQLite) trả datetime naive -> coi như UTC để so sánh.
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return self.used_at is None and expires_at > now

    def mark_used(self):
        self.used_at = _now()
        return self
