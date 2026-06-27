from ..extensions import db
from ..models.rbac import Permission


class PermissionRepository:
    def find_by_name(self, name):
        return Permission.query.filter_by(name=name).first()

    def all(self):
        return Permission.query.order_by(Permission.name).all()

    def add(self, permission):
        db.session.add(permission)
        return permission

    def commit(self):
        db.session.commit()
