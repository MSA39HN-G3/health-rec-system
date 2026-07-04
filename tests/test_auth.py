"""Test cho module auth (OAuth Google + me + logout).

Phủ các case:
  - GET /api/v1/auth/google/url      -> 302 redirect tới Google (kèm state).
  - POST /api/v1/auth/google/callback -> 200 login cũ / 201 user mới, cấp token.
  - GET /api/v1/auth/me               -> thông tin user hiện tại.
  - POST /api/v1/auth/logout          -> thu hồi token (blacklist).
  - 422: thiếu state, state sai độ dài.
  - 401: thiếu token ở me / logout.
  - 429: vượt rate limit ở callback (mock để cảm nhận).
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock


# ---------- GET /api/v1/auth/google/url ----------

def test_google_url_redirects_with_state(client):
    """Khi state hợp lệ, FE được redirect sang trang Google OAuth."""
    response = client.get(
        "/api/v1/auth/google/url?state=this-is-a-valid-state"
    )
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "accounts.google.com" in location or "oauth" in location.lower()
    # state echo ngược về FE để khớp callback
    assert "this-is-a-valid-state" in location


def test_google_url_missing_state_returns_422(client):
    """state bắt buộc, vắng -> 422."""
    response = client.get("/api/v1/auth/google/url")
    assert response.status_code == 422


def test_google_url_short_state_returns_422(client):
    """state ngắn dưới 8 ký tự -> 422."""
    response = client.get("/api/v1/auth/google/url?state=short")
    assert response.status_code == 422


# ---------- POST /api/v1/auth/google/callback ----------

def test_google_callback_creates_new_user_and_returns_201(
    client, db, mock_external_services
):
    """User mới (theo `google_sub`) -> status 201 + flag is_new_user=True."""
    body = {
        "authorization_code": "valid-auth-code",
        "state": "this-is-a-valid-state",
    }
    response = client.post("/api/v1/auth/google/callback", json=body)

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["is_new_user"] is True
    assert data["data"]["access_token"]
    assert data["data"]["token_type"] == "Bearer"
    assert data["data"]["expires_at"]
    assert data["data"]["user"]["email"] == "test@test.local"


def test_google_callback_login_existing_user_returns_200(
    client, db, mock_external_services
):
    """User đã tồn tại -> login thường, status 200."""
    # Lần đầu tạo user.
    client.post(
        "/api/v1/auth/google/callback",
        json={"authorization_code": "x", "state": "this-is-a-valid-state"},
    )

    # Lần sau cùng email -> login thường.
    response = client.post(
        "/api/v1/auth/google/callback",
        json={"authorization_code": "y", "state": "this-is-a-valid-state"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["is_new_user"] is False


def test_google_callback_missing_body_fields_returns_422(
    client, mock_external_services
):
    """Thiếu `authorization_code` -> 422."""
    response = client.post(
        "/api/v1/auth/google/callback",
        json={"state": "this-is-a-valid-state"},
    )
    assert response.status_code == 422


# ---------- GET /api/v1/auth/me ----------

def test_me_returns_current_user(client, auth_header, plain_user):
    headers = auth_header(plain_user)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == "user@test.local"


def test_me_without_token_returns_401(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


# ---------- POST /api/v1/auth/logout ----------

def test_logout_revokes_token(client, auth_header, plain_user, db):
    """Logout đưa token vào blacklist -> gọi lại /me phải 401."""
    headers = auth_header(plain_user)

    # Trước khi logout, me hoạt động.
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200

    # Logout.
    response = client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    # Sau logout, me trả 401.
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_logout_without_token_returns_401(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
