"""Repository cho bảng refresh_tokens.

Layer này chỉ thao tác DB, không có business logic. Service mới
``refresh_token_service`` sẽ dùng repository này kết hợp với user_repository
để thực hiện rotation/revoke.
"""
from datetime import datetime, timezone

from sqlalchemy import and_

from ..extensions import db
from ..models.refresh_token import RefreshToken


def _now():
    return datetime.now(timezone.utc)


class RefreshTokenRepository:
    def add(self, refresh_token):
        db.session.add(refresh_token)
        return refresh_token

    def commit(self):
        db.session.commit()

    def find_by_hash(self, token_hash):
        return (
            db.session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def find_active_by_hash(self, token_hash, now=None):
        """Tìm token active (chưa revoke, chưa hết hạn) theo hash."""
        now = now or _now()
        return (
            db.session.query(RefreshToken)
            .filter(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
            )
            .first()
        )

    def revoke_all_for_user(self, user_id, now=None):
        """Thu hồi MỌI refresh token còn active của user (logout mọi thiết bị).

        Trả về số bản ghi bị ảnh hưởng.
        """
        now = now or _now()
        result = (
            db.session.query(RefreshToken)
            .filter(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
            .all()
        )
        for record in result:
            record.revoked_at = now
        return len(result)