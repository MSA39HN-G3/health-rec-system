from ..extensions import db
from ..models.token_blacklist import TokenBlacklist


class TokenBlacklistRepository:
    def is_blacklisted(self, jti):
        return (
            db.session.query(TokenBlacklist.id).filter_by(jti=jti).first() is not None
        )

    def add(self, jti, expires_at):
        record = TokenBlacklist(jti=jti, expires_at=expires_at)
        db.session.add(record)
        return record

    def commit(self):
        db.session.commit()
