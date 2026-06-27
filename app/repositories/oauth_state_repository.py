from ..extensions import db
from ..models.oauth_state import OAuthState


class OAuthStateRepository:
    def find_by_state(self, state):
        return OAuthState.query.filter_by(state=state).first()

    def save(self, state, expires_at):
        """Lưu state mới; nếu đã tồn tại (chưa dùng) thì gia hạn lại."""
        record = self.find_by_state(state)
        if record is None:
            record = OAuthState(state=state, expires_at=expires_at)
            db.session.add(record)
        else:
            record.expires_at = expires_at
            record.used_at = None
        return record

    def add(self, record):
        db.session.add(record)
        return record

    def commit(self):
        db.session.commit()
