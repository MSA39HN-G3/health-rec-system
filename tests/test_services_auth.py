"""Unit test cho AuthService — phủ login_with_google (state, claims, new user,
disabled user), issue_token, logout (jti blacklist)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.errors import ForbiddenException, UnauthorizedException
from app.services.auth_service import AuthService


def _make_service(app, **overrides):
    user_repo = overrides.get("user_repo", MagicMock())
    state_repo = overrides.get("state_repo", MagicMock())
    blacklist_repo = overrides.get("blacklist_repo", MagicMock())
    svc = AuthService(
        user_repository=user_repo,
        oauth_state_repository=state_repo,
        token_blacklist_repository=blacklist_repo,
    )
    return svc, user_repo, state_repo, blacklist_repo


def _usable_state_record(expires_at=None):
    record = MagicMock()
    record.is_usable.return_value = True
    record.expires_at = expires_at or (
        datetime.now(timezone.utc) + timedelta(seconds=600)
    )
    return record


# ==========================================================================
# build_google_login
# ==========================================================================

class TestBuildGoogleLogin:
    def test_uses_provided_state(self, app):
        svc, _, state_repo, _ = _make_service(app)
        with patch(
            "app.services.auth_service.google_oauth.build_authorization_url",
            return_value="https://google.com/...",
        ) as p:
            result = svc.build_google_login("my-state")
        assert result["state"] == "my-state"
        assert result["auth_url"] == "https://google.com/..."
        state_repo.save.assert_called_once()
        state_repo.commit.assert_called_once()

    def test_generates_state_when_missing(self, app):
        svc, _, state_repo, _ = _make_service(app)
        with patch(
            "app.services.auth_service.google_oauth.build_authorization_url",
            return_value="https://google.com/...",
        ), patch(
            "app.services.auth_service.google_oauth.generate_state",
            return_value="auto-state",
        ):
            result = svc.build_google_login()
        assert result["state"] == "auto-state"


# ==========================================================================
# login_with_google
# ==========================================================================

class TestLoginWithGoogle:
    def test_new_user_onboarded(self, app):
        svc, u_repo, s_repo, _ = _make_service(app)
        s_repo.find_by_state.return_value = _usable_state_record()

        with patch(
            "app.services.auth_service.google_oauth.exchange_code_for_tokens",
            return_value={"id_token": "abc"},
        ), patch(
            "app.services.auth_service.google_oauth.verify_id_token",
            return_value={
                "sub": "g-1", "email": "u@x.local", "name": "U",
                "picture": None, "email_verified": True,
            },
        ):
            u_repo.find_by_google_sub.return_value = None
            user, is_new = svc.login_with_google("auth-code", "state-1")

        assert is_new is True
        u_repo.add.assert_called_once()
        u_repo.commit.assert_called_once()

    def test_existing_user_returns(self, app):
        svc, u_repo, s_repo, _ = _make_service(app)
        s_repo.find_by_state.return_value = _usable_state_record()

        existing = MagicMock()
        existing.is_active = True
        u_repo.find_by_google_sub.return_value = existing

        with patch(
            "app.services.auth_service.google_oauth.exchange_code_for_tokens",
            return_value={"id_token": "abc"},
        ), patch(
            "app.services.auth_service.google_oauth.verify_id_token",
            return_value={"sub": "g-1", "email": "u@x.local", "name": "U"},
        ):
            user, is_new = svc.login_with_google("auth-code", "state-1")

        assert is_new is False
        assert user is existing

    def test_no_state_raises_401(self, app):
        svc, _, s_repo, _ = _make_service(app)
        s_repo.find_by_state.return_value = None
        with pytest.raises(UnauthorizedException):
            svc.login_with_google("c", "missing")

    def test_state_already_used_raises_401(self, app):
        svc, _, s_repo, _ = _make_service(app)
        rec = MagicMock()
        rec.is_usable.return_value = False
        s_repo.find_by_state.return_value = rec
        with pytest.raises(UnauthorizedException):
            svc.login_with_google("c", "old")

    def test_state_marked_used(self, app):
        svc, _, s_repo, _ = _make_service(app)
        rec = _usable_state_record()
        s_repo.find_by_state.return_value = rec

        with patch(
            "app.services.auth_service.google_oauth.exchange_code_for_tokens",
            return_value={"id_token": "abc"},
        ), patch(
            "app.services.auth_service.google_oauth.verify_id_token",
            return_value={"sub": "g-1"},
        ):
            u_repo = MagicMock()
            svc.users = u_repo
            u_repo.find_by_google_sub.return_value = MagicMock(is_active=True)
            svc.login_with_google("c", "s")
        rec.mark_used.assert_called_once()

    def test_missing_id_token_raises(self, app):
        svc, _, s_repo, _ = _make_service(app)
        s_repo.find_by_state.return_value = _usable_state_record()
        with patch(
            "app.services.auth_service.google_oauth.exchange_code_for_tokens",
            return_value={"access_token": "y"},  # thiếu id_token
        ):
            with pytest.raises(UnauthorizedException):
                svc.login_with_google("c", "s")

    def test_disabled_user_raises_403(self, app):
        svc, u_repo, s_repo, _ = _make_service(app)
        s_repo.find_by_state.return_value = _usable_state_record()
        existing = MagicMock()
        existing.is_active = False
        u_repo.find_by_google_sub.return_value = existing
        with patch(
            "app.services.auth_service.google_oauth.exchange_code_for_tokens",
            return_value={"id_token": "abc"},
        ), patch(
            "app.services.auth_service.google_oauth.verify_id_token",
            return_value={"sub": "g-1"},
        ):
            with pytest.raises(ForbiddenException):
                svc.login_with_google("c", "s")


# ==========================================================================
# issue_token
# ==========================================================================

class TestIssueToken:
    def test_returns_token_and_expiry(self, app):
        svc, *_ = _make_service(app)
        with patch(
            "app.services.auth_service.token_service.issue_access_token",
            return_value=("token-xyz", "jti-123", datetime.now(timezone.utc)),
        ):
            token, expires_at = svc.issue_token(MagicMock())
        assert token == "token-xyz"
        assert expires_at is not None


# ==========================================================================
# logout
# ==========================================================================

class TestLogout:
    def test_adds_jti_to_blacklist(self, app):
        svc, _, _, bl = _make_service(app)
        bl.is_blacklisted.return_value = False
        payload = {"jti": "jti-1", "exp": int(datetime.now(timezone.utc).timestamp())}
        svc.logout(payload)
        bl.add.assert_called_once()
        bl.commit.assert_called_once()

    def test_already_blacklisted_noop(self, app):
        svc, _, _, bl = _make_service(app)
        bl.is_blacklisted.return_value = True
        payload = {"jti": "jti-1", "exp": 99999}
        svc.logout(payload)
        bl.add.assert_not_called()
        bl.commit.assert_not_called()

    def test_no_jti_returns(self, app):
        svc, _, _, bl = _make_service(app)
        svc.logout({})
        bl.add.assert_not_called()
        bl.commit.assert_not_called()

    def test_no_exp_uses_now(self, app):
        svc, _, _, bl = _make_service(app)
        bl.is_blacklisted.return_value = False
        svc.logout({"jti": "jti-1"})
        bl.add.assert_called_once()
