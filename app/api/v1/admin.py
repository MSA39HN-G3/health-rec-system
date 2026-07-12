"""Controller khu vực admin: quản lý user, role, permission (RBAC DB-driven).

Bảo vệ theo PERMISSION (không hard-code role), nên có thể đổi quyền của role
trong DB mà không cần sửa code:
  - user:read   -> xem danh sách user
  - user:manage -> gán/gỡ role cho user
  - role:manage -> tạo role, gán/gỡ permission cho role
"""
from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...i18n import translate
from ...middleware import (
    Field,
    current_user,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.auth_service import AuthService
from ...services.role_service import RoleService
from ...services.user_service import UserService

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

_user_service = UserService()
_role_service = RoleService()
_auth_service = AuthService()


# ----------------------------- Quản lý user ------------------------------

@bp.get("/users")
@require_permission(Permission.USER_READ)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def list_users():
    q = validated_query()
    items, total = _user_service.list_users(q["page"], q["size"])
    return paginated_response(
        [u.to_dict() for u in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.get("/users/search")
@require_permission(Permission.USER_READ)
@validate_query(
    {
        "keyword": Field(str, required=False, max_length=255),
        "role": Field(str, required=False, max_length=64),
        "is_active": Field(bool, required=False),
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def search_users():
    """Tìm kiếm và lọc user.

    Cách dùng:
      - Tìm theo từ khóa (email hoặc tên):
        GET /api/v1/admin/users/search?keyword=nguyen
      - Lọc theo role:
        GET /api/v1/admin/users/search?role=admin
      - Lọc theo trạng thái:
        GET /api/v1/admin/users/search?is_active=true
      - Kết hợp nhiều bộ lọc:
        GET /api/v1/admin/users/search?keyword=a&role=admin&is_active=true
    """
    q = validated_query()
    keyword = q.get("keyword")
    role = q.get("role")
    is_active = q.get("is_active")

    if keyword:
        items, total = _user_service.search_users(
            keyword, q["page"], q["size"]
        )
    else:
        items, total = _user_service.filter_users(
            q["page"], q["size"], role=role, is_active=is_active
        )

    return paginated_response(
        [u.to_dict() for u in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.get("/users/<int:user_id>")
@require_permission(Permission.USER_READ)
def get_user(user_id):
    """Lấy chi tiết một user (profile + roles + permissions)."""
    user = _user_service.get_user(user_id)
    return success_response({"user": user.to_dict()})


@bp.post("/users/<int:user_id>/roles")
@require_permission(Permission.USER_MANAGE)
@validate_body({"role": Field(str, required=True, min_length=1, max_length=64)})
def add_user_role(user_id):
    user = _user_service.add_role(user_id, validated()["role"])
    return success_response(
        {"user": user.to_dict()}, message=translate("messages.role_assigned")
    )


@bp.delete("/users/<int:user_id>/roles/<role_name>")
@require_permission(Permission.USER_MANAGE)
def remove_user_role(user_id, role_name):
    user = _user_service.remove_role(user_id, role_name)
    return success_response(
        {"user": user.to_dict()}, message=translate("messages.role_removed")
    )


@bp.patch("/users/<int:user_id>/status")
@require_permission(Permission.USER_MANAGE)
@validate_body({"is_active": Field(bool, required=True)})
def set_user_status(user_id):
    """Bật/tắt (disable) tài khoản user. Disable -> user bị chặn mọi thao tác."""
    user = _user_service.set_active(
        user_id, validated()["is_active"], acting_user_id=current_user().id
    )
    return success_response(
        {"user": user.to_dict()}, message=translate("messages.user_status_updated")
    )


# -------------------------- Quản lý role/permission ----------------------

@bp.get("/roles")
@require_permission(Permission.ROLE_MANAGE)
def list_roles():
    roles = _role_service.list_roles()
    return success_response([r.to_dict() for r in roles])


@bp.post("/roles")
@require_permission(Permission.ROLE_MANAGE)
@validate_body(
    {
        "name": Field(str, required=True, min_length=1, max_length=64),
        "description": Field(str, required=False, max_length=255),
    }
)
def create_role():
    data = validated()
    role = _role_service.create_role(data["name"], data.get("description"))
    return success_response(
        role.to_dict(),
        message=translate("messages.role_created"),
        status_code=201,
    )


@bp.post("/roles/<int:role_id>/permissions")
@require_permission(Permission.ROLE_MANAGE)
@validate_body({"permission": Field(str, required=True, min_length=1, max_length=64)})
def add_role_permission(role_id):
    role = _role_service.add_permission(role_id, validated()["permission"])
    return success_response(
        role.to_dict(), message=translate("messages.permission_assigned")
    )


@bp.delete("/roles/<int:role_id>/permissions/<permission_name>")
@require_permission(Permission.ROLE_MANAGE)
def remove_role_permission(role_id, permission_name):
    role = _role_service.remove_permission(role_id, permission_name)
    return success_response(
        role.to_dict(), message=translate("messages.permission_removed")
    )


@bp.get("/permissions")
@require_permission(Permission.ROLE_MANAGE)
def list_permissions():
    perms = _role_service.list_permissions()
    return success_response([p.to_dict() for p in perms])


# ------------------------- Token introspection (admin) ----------------------
#
# Cho phép admin kiểm tra trạng thái bất kỳ token nào của user (active/revoked/expired).
# Dùng khi debug "user bảo token vẫn còn nhưng request bị 403" hoặc khi revoke sạch
# các phiên của user bị vô hiệu hóa.
# Cần `user:read` (chỉ admin mặc định có).

@bp.post("/auth/introspect")
@require_permission(Permission.USER_READ)
@validate_body({"token": Field(str, required=True, min_length=1)})
def admin_introspect_token():
    """Admin introspect một token bất kỳ để kiểm tra trạng thái active.

    Body: `{ "token": "<JWT>" }`
    Trả về cùng cấu trúc như `/api/v1/auth/introspect`, nhưng có thêm audit
    thông tin về người gọi (`audited_by`) để truy vết trong log nếu cần.
    """
    data = validated()
    result = _auth_service.introspect_token(data["token"])
    result["audited_by"] = current_user().id
    return success_response(result)
