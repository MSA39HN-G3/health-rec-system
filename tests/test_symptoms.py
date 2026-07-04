"""Test cho module symptoms (categories + symptoms CRUD).

Categories là sub-resource của symptoms; bất kỳ ai cũng đọc được,
chỉ người có permission `symptom:manage` mới tạo/sửa/xoá.
"""
from __future__ import annotations


# ============================================================
# Categories
# ============================================================

def test_list_categories_does_not_require_auth(client):
    """GET /categories public."""
    response = client.get("/api/v1/symptoms/categories")
    assert response.status_code == 200
    assert response.get_json()["data"] == []


def test_create_category_requires_permission(client, auth_header, plain_user):
    response = client.post(
        "/api/v1/symptoms/categories",
        headers=auth_header(plain_user),
        json={"name": "Hô hấp"},
    )
    assert response.status_code == 403


def test_create_category_success(client, auth_header, admin_user):
    response = client.post(
        "/api/v1/symptoms/categories",
        headers=auth_header(admin_user),
        json={"name": "Hô hấp", "description": "Bệnh về đường hô hấp"},
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["name"] == "Hô hấp"
    assert data["description"] == "Bệnh về đường hô hấp"


def test_create_category_missing_name_returns_422(
    client, auth_header, admin_user
):
    response = client.post(
        "/api/v1/symptoms/categories",
        headers=auth_header(admin_user),
        json={"description": "không tên"},
    )
    assert response.status_code == 422


def test_get_category_not_found_returns_404(client):
    response = client.get("/api/v1/symptoms/categories/9999")
    assert response.status_code == 404


def test_update_category_partial(client, auth_header, admin_user):
    headers = auth_header(admin_user)
    client.post(
        "/api/v1/symptoms/categories",
        headers=headers,
        json={"name": "Hô hấp"},
    )

    response = client.patch(
        "/api/v1/symptoms/categories/1",
        headers=headers,
        json={"description": "Triệu chứng liên quan hệ hô hấp"},
    )
    assert response.status_code == 200
    assert (
        response.get_json()["data"]["description"]
        == "Triệu chứng liên quan hệ hô hấp"
    )
    # name không thay đổi
    assert response.get_json()["data"]["name"] == "Hô hấp"


def test_delete_category(client, auth_header, admin_user):
    headers = auth_header(admin_user)
    client.post(
        "/api/v1/symptoms/categories",
        headers=headers,
        json={"name": "Hô hấp"},
    )

    response = client.delete(
        "/api/v1/symptoms/categories/1", headers=headers
    )
    assert response.status_code == 200

    # Xoá xong -> get lại 404
    response = client.get("/api/v1/symptoms/categories/1")
    assert response.status_code == 404


def test_delete_category_without_permission_returns_403(
    client, auth_header, plain_user, admin_user
):
    headers_admin = auth_header(admin_user)
    client.post(
        "/api/v1/symptoms/categories",
        headers=headers_admin,
        json={"name": "Hô hấp"},
    )

    response = client.delete(
        "/api/v1/symptoms/categories/1", headers=auth_header(plain_user)
    )
    assert response.status_code == 403


# ============================================================
# Symptoms
# ============================================================

def _seed_category():
    """Trả về dict đại diện 1 category."""
    return {"id": 1, "name": "Hô hấp"}


def test_list_symptoms_default(client):
    response = client.get("/api/v1/symptoms")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["total"] == 0


def test_list_symptoms_validates_size(client):
    response = client.get("/api/v1/symptoms?size=999")
    assert response.status_code == 422


def test_create_symptom_requires_permission(
    client, auth_header, plain_user
):
    response = client.post(
        "/api/v1/symptoms",
        headers=auth_header(plain_user),
        json={"code": "S-001", "name": "Ho khan"},
    )
    assert response.status_code == 403


def test_create_symptom_success(client, auth_header, admin_user):
    headers = auth_header(admin_user)

    # Tạo category trước để liên kết.
    client.post(
        "/api/v1/symptoms/categories",
        headers=headers,
        json={"name": "Hô hấp"},
    )

    response = client.post(
        "/api/v1/symptoms",
        headers=headers,
        json={
            "code": "S-001",
            "name": "Ho khan",
            "description": "ho không ra đờm",
            "category_id": 1,
            "synonyms": ["ho không đờm", "dry cough"],
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["code"] == "S-001"
    assert data["name"] == "Ho khan"
    assert data["synonyms"] == ["ho không đờm", "dry cough"]


def test_create_symptom_missing_required_returns_422(
    client, auth_header, admin_user
):
    """Bỏ `code` -> 422."""
    response = client.post(
        "/api/v1/symptoms",
        headers=auth_header(admin_user),
        json={"name": "Ho khan"},
    )
    assert response.status_code == 422


def test_get_symptom_not_found_returns_404(client):
    response = client.get("/api/v1/symptoms/9999")
    assert response.status_code == 404


def test_update_symptom_partial(client, auth_header, admin_user):
    headers = auth_header(admin_user)
    client.post(
        "/api/v1/symptoms",
        headers=headers,
        json={"code": "S-001", "name": "Ho khan"},
    )

    response = client.patch(
        "/api/v1/symptoms/1",
        headers=headers,
        json={"description": "mô tả mới"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["description"] == "mô tả mới"
    assert data["name"] == "Ho khan"  # giữ nguyên


def test_deactivate_symptom(client, auth_header, admin_user):
    headers = auth_header(admin_user)
    client.post(
        "/api/v1/symptoms",
        headers=headers,
        json={"code": "S-001", "name": "Ho khan"},
    )

    response = client.delete(
        "/api/v1/symptoms/1", headers=headers
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["is_active"] is False
