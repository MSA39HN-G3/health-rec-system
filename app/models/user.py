from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    google_sub = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255))
    picture = db.Column(db.String(512))
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    def apply_google_claims(self, claims):
        self.email = claims.get("email")
        self.full_name = claims.get("name")
        self.picture = claims.get("picture")
        self.email_verified = bool(claims.get("email_verified", False))
        self.last_login_at = _now()
        return self

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "picture": self.picture,
            "email_verified": self.email_verified,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
