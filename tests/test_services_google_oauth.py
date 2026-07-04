"""Unit test cho google_oauth service — phủ sinh state, build URL, exchange code, verify id_token."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.errors import AppException, UnauthorizedException
from app.services import google_oauth


# ==========================================================================
# generate_state
# ==========================================================================

class TestGenerateState:
    def test_returns_string(self):
        s = google_oauth.generate_state()
        assert isinstance(s, str)
        assert len(s) >= 16  # token_urlsafe(32) → ~43 chars

    def test_each_call_unique(self):
        a, b = google_oauth.generate_state(), google_oauth.generate_state()
        assert a != b


# ==========================================================================
# _require_config
# ==========================================================================

class TestRequireConfig:
    def test_missing_raises_500(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["GOOGLE_CLIENT_ID"] = ""
            current_app.config["GOOGLE_CLIENT_SECRET"] = ""
            with pytest.raises(AppException):
                google_oauth._require_config()


# ==========================================================================
# build_authorization_url
# ==========================================================================

class TestBuildAuthorizationUrl:
    def test_returns_url_with_state_and_params(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["GOOGLE_CLIENT_ID"] = "cid"
            current_app.config["GOOGLE_CLIENT_SECRET"] = "csec"
            current_app.config["GOOGLE_REDIRECT_URI"] = "http://x/cb"
            url = google_oauth.build_authorization_url("abc-state")
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=c" in url  # url-encoded "cid"
        assert "state=abc-state" in url
        assert "response_type=code" in url
        assert "scope=openid" in url

    def test_missing_config_raises(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["GOOGLE_CLIENT_ID"] = ""
            current_app.config["GOOGLE_CLIENT_SECRET"] = "x"
            with pytest.raises(AppException):
                google_oauth.build_authorization_url("s")


# ==========================================================================
# exchange_code_for_tokens
# ==========================================================================

class TestExchangeCodeForTokens:
    def test_returns_dict_on_200(self, app):
        with patch.object(google_oauth.requests, "post") as p:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"access_token": "x"}
            p.return_value = resp

            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                current_app.config["GOOGLE_CLIENT_SECRET"] = "csec"
                tokens = google_oauth.exchange_code_for_tokens("auth-code")

        assert tokens == {"access_token": "x"}
        args, kwargs = p.call_args
        assert kwargs["data"]["code"] == "auth-code"
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["timeout"] == 10

    def test_network_error_raises_502(self, app):
        with patch.object(
            google_oauth.requests, "post",
            side_effect=requests.ConnectionError(),
        ):
            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                current_app.config["GOOGLE_CLIENT_SECRET"] = "csec"
                with pytest.raises(AppException):
                    google_oauth.exchange_code_for_tokens("code")

    def test_non_200_raises_401(self, app):
        with patch.object(google_oauth.requests, "post") as p:
            resp = MagicMock()
            resp.status_code = 400
            resp.json.return_value = {"error": "invalid_grant"}
            p.return_value = resp

            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                current_app.config["GOOGLE_CLIENT_SECRET"] = "csec"
                with pytest.raises(UnauthorizedException):
                    google_oauth.exchange_code_for_tokens("code")

    def test_non_200_with_invalid_json(self, app):
        """Body không phải JSON vẫn raise 401 với details=None."""
        with patch.object(google_oauth.requests, "post") as p:
            resp = MagicMock()
            resp.status_code = 400
            resp.json.side_effect = ValueError()
            p.return_value = resp

            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                current_app.config["GOOGLE_CLIENT_SECRET"] = "csec"
                with pytest.raises(UnauthorizedException):
                    google_oauth.exchange_code_for_tokens("code")


# ==========================================================================
# verify_id_token
# ==========================================================================

class TestVerifyIdToken:
    def test_returns_claims_on_ok(self, app):
        with patch.object(google_oauth.google_id_token, "verify_oauth2_token") as v:
            v.return_value = {"sub": "g-1", "email": "a@b"}
            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                claims = google_oauth.verify_id_token("tok")
        assert claims == {"sub": "g-1", "email": "a@b"}
        # verify_oauth2_token(token, request, audience, clock_skew_in_seconds=...)
        args, kwargs = v.call_args
        assert args[0] == "tok"
        assert kwargs["clock_skew_in_seconds"] == 10
        # audience truyền positionally
        assert "cid" in args

    def test_invalid_token_raises_401(self, app):
        with patch.object(
            google_oauth.google_id_token, "verify_oauth2_token",
            side_effect=ValueError("bad"),
        ):
            from flask import current_app
            with app.app_context():
                current_app.config["GOOGLE_CLIENT_ID"] = "cid"
                with pytest.raises(UnauthorizedException):
                    google_oauth.verify_id_token("tok")
