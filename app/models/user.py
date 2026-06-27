from datetime import datetime, timezone

from ..extensions import db
from .rbac import user_roles


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
    # Trạng thái tài khoản. False = bị vô hiệu hóa (chặn mọi thao tác).
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    # RBAC: 1 user có nhiều role (nhiều-nhiều). User mới onboard chưa có role nào.
    roles = db.relationship(
        "Role",
        secondary=user_roles,
        backref=db.backref("users", lazy="dynamic"),
        lazy="joined",
    )

    def role_names(self):
        return {r.name for r in self.roles}

    def permission_names(self):
        """Tập hợp permission từ tất cả role mà user có."""
        names = set()
        for role in self.roles:
            names |= role.permission_names()
        return names

    def has_role(self, *names):
        """True nếu user có ít nhất một trong các role truyền vào."""
        return not self.role_names().isdisjoint(names)

    def has_permission(self, *names):
        """True nếu user có ít nhất một trong các permission truyền vào."""
        return not self.permission_names().isdisjoint(names)

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
            "is_active": self.is_active,
            "roles": sorted(self.role_names()),
            "permissions": sorted(self.permission_names()),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
