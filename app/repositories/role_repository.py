from ..extensions import db
from ..models.rbac import Role


class RoleRepository:
    def find_by_id(self, role_id):
        return db.session.get(Role, role_id)

    def find_by_name(self, name):
        return Role.query.filter_by(name=name).first()

    def all(self):
        return Role.query.order_by(Role.name).all()

    def add(self, role):
        db.session.add(role)
        return role

    def commit(self):
        db.session.commit()
