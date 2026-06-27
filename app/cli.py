"""Các lệnh CLI hỗ trợ vận hành RBAC.

    flask --app run seed-rbac                         # tạo role & permission mặc định
    flask --app run grant-role user@example.com admin # gán role cho user
"""
import click

from .common.roles import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    Permission,
    Role,
)
from .extensions import db
from .models.rbac import Permission as PermissionModel
from .models.rbac import Role as RoleModel
from .repositories.user_repository import UserRepository


def seed_rbac():
    """Tạo (nếu chưa có) toàn bộ permission, role và gán permission mặc định cho role."""
    # 1. Permissions
    perms = {}
    for name in Permission.ALL:
        perm = PermissionModel.query.filter_by(name=name).first()
        if perm is None:
            perm = PermissionModel(
                name=name, description=PERMISSION_DESCRIPTIONS.get(name)
            )
            db.session.add(perm)
        perms[name] = perm

    # 2. Roles + gán permission mặc định
    for role_name in Role.ALL:
        role = RoleModel.query.filter_by(name=role_name).first()
        if role is None:
            role = RoleModel(name=role_name)
            db.session.add(role)
        for perm_name in DEFAULT_ROLE_PERMISSIONS.get(role_name, []):
            perm = perms[perm_name]
            if perm not in role.permissions:
                role.permissions.append(perm)

    db.session.commit()


def register_cli(app):
    @app.cli.command("seed-rbac")
    def seed_rbac_command():
        """Khởi tạo role & permission mặc định (idempotent)."""
        seed_rbac()
        click.echo("Đã seed RBAC: roles=%s" % ", ".join(Role.ALL))

    @app.cli.command("grant-role")
    @click.argument("email")
    @click.argument("role")
    def grant_role(email, role):
        """Gán ROLE cho user theo EMAIL (vd: admin)."""
        role_model = RoleModel.query.filter_by(name=role).first()
        if role_model is None:
            click.echo(f"Role không tồn tại: {role}. Hãy chạy seed-rbac trước.")
            return
        user = UserRepository().find_by_email(email)
        if user is None:
            click.echo(f"Không tìm thấy user: {email}")
            return
        if role_model not in user.roles:
            user.roles.append(role_model)
            db.session.commit()
        click.echo(f"Đã gán role '{role}' cho {email}. Roles hiện tại: {sorted(user.role_names())}")
