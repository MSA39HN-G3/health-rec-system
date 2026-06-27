"""Middleware xác thực JWT cho các endpoint cần đăng nhập.

Dùng decorator `@require_auth` trên controller. Quy trình verify:
    1. Đọc token từ header `Authorization: Bearer <token>`.
    2. Giải mã & kiểm tra chữ ký/hạn dùng (token_service.decode_token).
    3. Kiểm tra `jti` có trong blacklist không (đã logout/thu hồi) -> nếu có thì chặn.
    4. Nạp user tương ứng vào `g.current_user` để controller dùng.
"""
from functools import wraps

import jwt
from flask import g, request

from ..errors import ForbiddenException, UnauthorizedException
from ..repositories.token_blacklist_repository import TokenBlacklistRepository
from ..repositories.user_repository import UserRepository
from ..services import token_service

_blacklist = TokenBlacklistRepository()
_users = UserRepository()


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()

        try:
            payload = token_service.decode_token(token)
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("errors.token_expired")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("errors.token_invalid")

        jti = payload.get("jti")
        if jti and _blacklist.is_blacklisted(jti):
            raise UnauthorizedException("errors.token_revoked")

        user = _users.find_by_id(_to_int(payload.get("sub")))
        if user is None:
            raise UnauthorizedException("errors.token_invalid")

        # Lưu ngữ cảnh cho controller và endpoint logout.
        g.current_user = user
        g.jwt_payload = payload
        g.jwt_token = token
        return fn(*args, **kwargs)

    return wrapper


def require_role(*roles):
    """Yêu cầu user đã đăng nhập VÀ có ít nhất một trong các role cho phép.

    Dùng: @require_role(Role.ADMIN) hoặc @require_role(Role.DOCTOR, Role.DEPARTMENT_HEAD).
    Chưa đăng nhập -> 401; đã đăng nhập nhưng thiếu role -> 403.
    """

    def decorator(fn):
        @require_auth
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not g.current_user.has_role(*roles):
                raise ForbiddenException()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(*permissions):
    """Yêu cầu user đã đăng nhập VÀ có ít nhất một trong các permission cho phép.

    Dùng: @require_permission(Permission.USER_MANAGE).
    Chưa đăng nhập -> 401; đã đăng nhập nhưng thiếu permission -> 403.
    """

    def decorator(fn):
        @require_auth
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not g.current_user.has_permission(*permissions):
                raise ForbiddenException()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise UnauthorizedException("errors.token_missing")
    return parts[1]


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def current_user():
    """Lấy user đã xác thực của request hiện tại (None nếu chưa qua require_auth)."""
    return getattr(g, "current_user", None)
