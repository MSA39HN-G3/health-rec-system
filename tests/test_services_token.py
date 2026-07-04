"""Unit test cho token_service — phủ cấp JWT và giải mã."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services import token_service


# ==========================================================================
# issue_access_token
# ==========================================================================

class TestIssueAccessToken:
    def test_returns_jwt_with_required_claims(self, app, plain_user):
        with app.app_context():
            token, jti, expires_at = token_service.issue_access_token(plain_user)

        assert isinstance(token, str) and len(token) > 20
        assert isinstance(jti, str) and len(jti) >= 16

        # Decode để kiểm tra payload.
        with app.app_context():
            payload = token_service.decode_token(token)
        assert payload["sub"] == str(plain_user.id)
        assert payload["jti"] == jti
        assert payload["type"] == "access"
        assert "iat" in payload and "exp" in payload

    def test_expiry_is_in_future(self, app, plain_user):
        with app.app_context():
            _, _, expires_at = token_service.issue_access_token(plain_user)
        # expires_at phải > now()
        assert expires_at > datetime.now(timezone.utc) - timedelta(seconds=5)


# ==========================================================================
# decode_token
# ==========================================================================

class TestDecodeToken:
    def test_invalid_signature_raises(self, app):
        from flask import current_app

        # Tạo token với secret SAI.
        forged = jwt.encode(
            {"sub": "1", "jti": "x", "type": "access", "exp": 9999999999},
            "wrong-secret",
            algorithm="HS256",
        )
        with app.app_context():
            current_app.config["JWT_SECRET"] = "test-secret"
            with pytest.raises(jwt.InvalidTokenError):
                token_service.decode_token(forged)

    def test_expired_raises(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["JWT_SECRET"] = "test-secret"
            expired = jwt.encode(
                {
                    "sub": "1", "jti": "x", "type": "access",
                    "iat": 1, "exp": 100,
                },
                "test-secret",
                algorithm="HS256",
            )
            with pytest.raises(jwt.ExpiredSignatureError):
                token_service.decode_token(expired)
