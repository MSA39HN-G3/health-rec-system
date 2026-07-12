"""Model cho refresh token (opaque).

Mỗi bản ghi đại diện cho một refresh token còn hiệu lực. Hệ thống chỉ lưu
**SHA-256 hash** của raw token; raw token chỉ tồn tại ở phía client (FE) và
được gửi lên BE khi cần refresh.

Rotation: mỗi lần refresh thành công sẽ tạo token mới và đánh dấu token cũ
là ``revoked_at = now()``. ``parent_id`` cho phép truy vết chuỗi token theo
user để hỗ trợ reuse detection.
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Integer

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


def _as_aware(dt):
    """Đảm bảo datetime có tzinfo (SQLite có thể trả naive khi load)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Trên SQLite, BigInteger không tự động thành INTEGER PRIMARY KEY (cần thiết cho
# auto-increment). Dùng ``with_variant`` để chuyển sang Integer khi chạy trên SQLite
# (chỉ dùng cho test); trên Postgres vẫn giữ BigInteger cho production.
_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest của raw token (64 hex chars).
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    # Chuỗi huyết thống: parent_id = id của token bị xoay vòng.
    parent_id = db.Column(
        _BIGINT_PK,
        db.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Audit: IP + user-agent tạo token.
    created_ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_now
    )

    # ----- tiện ích -----
    def is_active(self, now=None):
        """True nếu token chưa bị thu hồi và chưa hết hạn."""
        if self.revoked_at is not None:
            return False
        return _as_aware(self.expires_at) > (now or _now())

    def revoke(self, now=None):
        """Đánh dấu token đã bị thu hồi (idempotent)."""
        if self.revoked_at is None:
            self.revoked_at = now or _now()

    def to_dict(self):
        def fmt(dt):
            d = _as_aware(dt)
            return d.isoformat() if d else None

        return {
            "id": self.id,
            "user_id": self.user_id,
            "parent_id": self.parent_id,
            "expires_at": fmt(self.expires_at),
            "revoked_at": fmt(self.revoked_at),
            "created_at": fmt(self.created_at),
        }