"""Test cho module uploads (presign + confirm).

Phủ:
  - POST /presign trả URL presigned (mock R2) cho avatar.
  - Validate content_type / size.
  - POST /confirm HEAD object trên R2 -> URL đọc.
  - Confirm object_key không hợp lệ -> 404.
  - Confirm khi R2 báo object chưa tồn tại -> 404.
  - Không có token -> 401 ở cả 2 endpoint.
"""
from __future__ import annotations


# ---------- /uploads/presign ----------

def test_presign_requires_auth(client, mock_external_services):
    response = client.post(
        "/api/v1/uploads/presign",
        json={
            "kind": "avatar",
            "content_type": "image/png",
            "size": 1024,
        },
    )
    assert response.status_code == 401


def test_presign_returns_signed_put(
    client, auth_header, plain_user, mock_external_services
):
    response = client.post(
        "/api/v1/uploads/presign",
        headers=auth_header(plain_user),
        json={
            "kind": "avatar",
            "content_type": "image/png",
            "size": 2048,
            "filename": "me.png",
        },
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["method"] == "PUT"
    assert data["url"].startswith("https://")
    assert data["kind"] == "avatar"
    assert data["object_key"]
    assert data["expires_in"]


def test_presign_missing_kind_returns_422(
    client, auth_header, plain_user, mock_external_services
):
    response = client.post(
        "/api/v1/uploads/presign",
        headers=auth_header(plain_user),
        json={"content_type": "image/png", "size": 1000},
    )
    assert response.status_code == 422


def test_presign_zero_size_returns_422(
    client, auth_header, plain_user, mock_external_services
):
    response = client.post(
        "/api/v1/uploads/presign",
        headers=auth_header(plain_user),
        json={"kind": "avatar", "content_type": "image/png", "size": 0},
    )
    assert response.status_code == 422


def test_presign_size_too_big_returns_422(
    client, auth_header, plain_user, mock_external_services
):
    """Vượt 100MB (trần middleware) -> 422."""
    response = client.post(
        "/api/v1/uploads/presign",
        headers=auth_header(plain_user),
        json={
            "kind": "avatar",
            "content_type": "image/png",
            "size": 200 * 1024 * 1024,  # 200MB
        },
    )
    assert response.status_code == 422


# ---------- /uploads/confirm ----------

def test_confirm_requires_auth(client, mock_external_services):
    response = client.post(
        "/api/v1/uploads/confirm",
        json={"kind": "avatar", "object_key": "avatar/abc.png"},
    )
    assert response.status_code == 401


def test_confirm_returns_signed_get(
    client, auth_header, plain_user, mock_external_services
):
    response = client.post(
        "/api/v1/uploads/confirm",
        headers=auth_header(plain_user),
        json={
            "kind": "avatar",
            "object_key": "avatar/abc.png",
            "content_type": "image/png",
        },
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["url"].startswith("https://")
    assert data["object_key"] == "avatar/abc.png"
    assert data["expires_in"]


def test_confirm_invalid_object_key_returns_404(
    client, auth_header, plain_user, mock_external_services, monkeypatch
):
    """object_key không khớp định dạng (vd chứa `..`) -> 404."""
    from app.services import storage as _storage_mod
    monkeypatch.setattr(
        _storage_mod, "is_valid_object_key", lambda key: False
    )

    response = client.post(
        "/api/v1/uploads/confirm",
        headers=auth_header(plain_user),
        json={"kind": "avatar", "object_key": "../etc/passwd"},
    )
    assert response.status_code == 404


def test_confirm_missing_object_returns_404(
    client, auth_header, plain_user, mock_external_services, monkeypatch
):
    """head_exists trả False (object chưa upload lên) -> 404."""
    from app.services import storage as _storage_mod
    monkeypatch.setattr(_storage_mod, "head_exists", lambda key: False)

    response = client.post(
        "/api/v1/uploads/confirm",
        headers=auth_header(plain_user),
        json={"kind": "avatar", "object_key": "avatar/missing.png"},
    )
    assert response.status_code == 404


def test_confirm_missing_kind_returns_422(
    client, auth_header, plain_user, mock_external_services
):
    response = client.post(
        "/api/v1/uploads/confirm",
        headers=auth_header(plain_user),
        json={"object_key": "avatar/abc.png"},
    )
    assert response.status_code == 422
