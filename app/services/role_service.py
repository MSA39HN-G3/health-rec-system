"""Service quản lý role & permission (khu vực admin)."""
from ..errors import ConflictException, NotFoundException
from ..models.rbac import Role
from ..repositories.permission_repository import PermissionRepository
from ..repositories.role_repository import RoleRepository


class RoleService:
    def __init__(self, role_repository=None, permission_repository=None):
        self.roles = role_repository or RoleRepository()
        self.permissions = permission_repository or PermissionRepository()

    def list_roles(self):
        return self.roles.all()

    def list_permissions(self):
        return self.permissions.all()

    def create_role(self, name, description=None):
        if self.roles.find_by_name(name) is not None:
            raise ConflictException("errors.role_exists")
        role = Role(name=name, description=description)
        self.roles.add(role)
        self.roles.commit()
        return role

    def add_permission(self, role_id, permission_name):
        """Gán thêm một permission (theo tên) cho role."""
        role = self.roles.find_by_id(role_id)
        if role is None:
            raise NotFoundException("errors.role_not_found")
        permission = self.permissions.find_by_name(permission_name)
        if permission is None:
            raise NotFoundException("errors.permission_not_found")
        if permission not in role.permissions:
            role.permissions.append(permission)
            self.roles.commit()
        return role

    def remove_permission(self, role_id, permission_name):
        role = self.roles.find_by_id(role_id)
        if role is None:
            raise NotFoundException("errors.role_not_found")
        permission = self.permissions.find_by_name(permission_name)
        if permission is not None and permission in role.permissions:
            role.permissions.remove(permission)
            self.roles.commit()
        return role
