"""Unit test cho AuthService.introspect_token — phủ 4 nhánh kết quả:
  - token hợp lệ + user còn active -> active=True (có sub/jti/exp/expires_in/user)
  - token đã hết hạn -> active=False, reason="expired"
  - token bị thu hồi (blacklist) -> active=False, reason="revoked"
  - token hợp lệ nhưng user bị xoá -> active=False, reason="user_not_found"
  - token sai chữ ký -> active=False, reason="invalid"
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.services import token_service
from app.services.auth_service import AuthService


def _make_service(user_repo=None, blacklist_repo=None):
    return AuthService(
        user_repository=user_repo or MagicMock(),
        oauth_state_repository=MagicMock(),
        token_blacklist_repository=blacklist_repo or MagicMock(),
    ), user_repo, blacklist_repo


def _issue_token(app, sub="1", jti="jti-x", exp_offset=3600):
    """Sinh token thật bằng token_service để chắc chắn decode được."""
    with app.app_context():
        token, _, _ = token_service.issue_access_token.__wrapped__ if False else (
            lambda u: (
                token_service.issue_access_token(
                    _user_like(u, jti=jti, exp_offset=exp_offset)
                )
                if False
                else None
            )
        ), None
    # Dùng trực tiếp token_service đơn giản
    return _issue_raw(app, sub=sub, jti=jti, exp_offset=exp_offset)


def _user_like(user, jti=None, exp_offset=3600):
    return user


def _issue_raw(app, sub="1", jti="jti-x", exp_offset=3600):
    """Sinh JWT thật bằng config của app."""
    import uuid
    cfg = app.config
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_offset)).timestamp()),
    }
    return jwt.encode(payload, cfg["JWT_SECRET"], algorithm=cfg["JWT_ALGORITHM"])


def _make_user(id=1, is_active=True, role_names=None, perm_names=None):
    user = MagicMock()
    user.id = id
    user.is_active = is_active
    user.role_names.return_value = set(role_names or [])
    user.permission_names.return_value = set(perm_names or [])
    return user


# ==========================================================================
# active = True
# ==========================================================================

class TestIntrospectActive:
    def test_returns_active_with_user_metadata(self, app):
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        blacklist_repo.is_blacklisted.return_value = False
        user = _make_user(
            id=42, is_active=True, role_names=["admin"], perm_names=["user:read"]
        )
        user_repo.find_by_id.return_value = user

        svc, _, _ = _make_service(user_repo, blacklist_repo)
        token = _issue_raw(app, sub="42", jti="abc")

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is True
        assert result["sub"] == "42"
        assert result["jti"] == "abc"
        assert result["type"] == "access"
        assert isinstance(result["iat"], int)
        assert isinstance(result["exp"], int)
        assert result["expires_in"] > 0
        assert result["user"]["id"] == 42
        assert result["user"]["is_active"] is True
        assert "admin" in result["user"]["roles"]
        assert "user:read" in result["user"]["permissions"]

    def test_active_user_with_no_roles(self, app):
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        blacklist_repo.is_blacklisted.return_value = False
        user = _make_user(id=5)
        user_repo.find_by_id.return_value = user

        svc, _, _ = _make_service(user_repo, blacklist_repo)
        token = _issue_raw(app, sub="5")

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is True
        assert result["user"]["roles"] == []
        assert result["user"]["permissions"] == []


# ==========================================================================
# active = False (các nhánh lỗi)
# ==========================================================================

class TestIntrospectInactive:
    def test_expired_token(self, app):
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        svc, _, _ = _make_service(user_repo, blacklist_repo)

        # exp_offset âm -> token đã hết hạn ngay khi decode
        token = _issue_raw(app, sub="1", exp_offset=-10)

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is False
        assert result["reason"] == "expired"
        # Không lộ thông tin user.
        assert "user" not in result
        assert "sub" not in result

    def test_invalid_signature(self, app):
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        svc, _, _ = _make_service(user_repo, blacklist_repo)

        with app.app_context():
            cfg = app.config
            now = int(time.time())
            # Token ký bằng secret sai -> InvalidTokenError.
            bad = jwt.encode(
                {"sub": "1", "jti": "x", "iat": now, "exp": now + 60, "type": "access"},
                "wrong-secret",
                algorithm=cfg["JWT_ALGORITHM"],
            )
            result = svc.introspect_token(bad)

        assert result["active"] is False
        assert result["reason"] == "invalid"

    def test_revoked_token_in_blacklist(self, app):
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        blacklist_repo.is_blacklisted.return_value = True

        svc, _, _ = _make_service(user_repo, blacklist_repo)
        token = _issue_raw(app, sub="1", jti="revoked-jti")

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is False
        assert result["reason"] == "revoked"
        assert "user" not in result

    def test_user_not_found(self, app):
        user_repo = MagicMock()
        user_repo.find_by_id.return_value = None
        blacklist_repo = MagicMock()
        blacklist_repo.is_blacklisted.return_value = False

        svc, _, _ = _make_service(user_repo, blacklist_repo)
        token = _issue_raw(app, sub="999")

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is False
        assert result["reason"] == "user_not_found"

    def test_invalid_sub_not_int(self, app):
        """Token có sub không phải số -> coi như không tìm được user."""
        user_repo = MagicMock()
        blacklist_repo = MagicMock()
        blacklist_repo.is_blacklisted.return_value = False

        svc, _, _ = _make_service(user_repo, blacklist_repo)
        token = _issue_raw(app, sub="not-a-number")

        with app.app_context():
            result = svc.introspect_token(token)

        assert result["active"] is False
        assert result["reason"] == "user_not_found"