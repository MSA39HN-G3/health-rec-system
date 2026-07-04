"""Test cho module departments (list, stats, create, update).

Lưu ý quan trọng: Mỗi endpoint admin (CREATE/UPDATE) đều yêu cầu permission
`department:manage`. Khi gọi không có user đăng nhập -> 401. Khi có user
nhưng thiếu permission -> 403.
"""
from __future__ import annotations

# ---------- helpers ----------

def _seed_departments(db, count=3):
    """Tạo `count` khoa để test pagination / stats."""
    from app.repositories import department_repository

    out = []
    for i in range(count):
        d = department_repository.create(
            name=f"Khoa test {i}",
            location=f"tầng {i}",
            description=f"mô tả {i}",
            keywords=[],
            conditions=[],
            ai_metadata={},
            head_doctor_id=None,
            is_active=(i % 2 == 0),  # xen kẽ active/inactive
        )
        out.append(d)
    db.session.commit()
    return out


# ---------- list_departments ----------

def test_list_departments_requires_permission(client):
    """Không có token -> 401."""
    response = client.get("/api/v1/departments")
    assert response.status_code == 401


def test_list_departments_with_permission_paginates(
    client, auth_header, admin_user, db
):
    _seed_departments(db, count=5)
    headers = auth_header(admin_user)

    response = client.get("/api/v1/departments?page=1&size=2", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["size"] == 2
    assert body["pagination"]["total"] == 5
    assert len(body["data"]) == 2


def test_list_departments_without_permission_returns_403(
    client, auth_header, plain_user
):
    """User thường (không có department:manage) -> 403."""
    response = client.get(
        "/api/v1/departments", headers=auth_header(plain_user)
    )
    assert response.status_code == 403


def test_list_departments_validates_query(
    client, auth_header, admin_user
):
    """size > 100 bị reject 422."""
    response = client.get(
        "/api/v1/departments?page=1&size=200", headers=auth_header(admin_user)
    )
    assert response.status_code == 422


# ---------- department_stats ----------

def test_stats_returns_totals(client, auth_header, admin_user, db):
    _seed_departments(db, count=4)
    headers = auth_header(admin_user)

    response = client.get("/api/v1/departments/stats", headers=headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 4
    # Trong _seed_departments, 0, 2 active; 1, 3 inactive.
    assert data["active"] == 2
    assert data["inactive"] == 2


# ---------- create_department ----------

def test_create_department_returns_201_and_returns_code(
    client, auth_header, admin_user
):
    headers = auth_header(admin_user)
    response = client.post(
        "/api/v1/departments",
        headers=headers,
        json={
            "name": "Khoa Nội",
            "location": "Tầng 3",
            "description": "Khám nội tổng quát",
            "keywords": ["nội", "tổng quát"],
            "conditions": ["đau bụng", "sốt"],
            "ai_metadata": {"priority": "high"},
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["name"] == "Khoa Nội"
    assert data["location"] == "Tầng 3"
    assert data["keywords"] == ["nội", "tổng quát"]
    assert data["conditions"] == ["đau bụng", "sốt"]
    # BE tự cấp mã khoa `CK-XXX`.
    assert data["code"].startswith("CK-")


def test_create_department_requires_name(client, auth_header, admin_user):
    """name bắt buộc, vắng -> 422."""
    response = client.post(
        "/api/v1/departments",
        headers=auth_header(admin_user),
        json={"location": "Tầng 1"},
    )
    assert response.status_code == 422


def test_create_department_rejects_long_name(client, auth_header, admin_user):
    """name > 255 ký tự -> 422."""
    response = client.post(
        "/api/v1/departments",
        headers=auth_header(admin_user),
        json={"name": "x" * 256},
    )
    assert response.status_code == 422


def test_create_department_invalid_keywords_returns_422(
    client, auth_header, admin_user
):
    """keywords phải là list[string]; truyền list[int] -> 422."""
    response = client.post(
        "/api/v1/departments",
        headers=auth_header(admin_user),
        json={
            "name": "Khoa Test",
            "keywords": [1, 2, 3],
        },
    )
    assert response.status_code == 422


def test_create_department_active_without_head_returns_400(
    client, auth_header, admin_user
):
    """is_active=true mà chưa có head_doctor_id hợp lệ -> 400 (business rule)."""
    response = client.post(
        "/api/v1/departments",
        headers=auth_header(admin_user),
        json={"name": "Khoa cần head", "is_active": True},
    )
    assert response.status_code == 400


# ---------- update_department ----------

def test_update_department_partial(client, auth_header, admin_user, db):
    """PATCH chỉ thay đổi những field có trong body."""
    _seed_departments(db, count=1)
    headers = auth_header(admin_user)

    response = client.patch(
        "/api/v1/departments/1",
        headers=headers,
        json={"location": "Tầng 5"},
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["location"] == "Tầng 5"
    # name giữ nguyên
    assert data["name"] == "Khoa test 0"


def test_update_department_empty_body_returns_422(
    client, auth_header, admin_user, db
):
    """Body rỗng -> 422 (no_fields)."""
    _seed_departments(db, count=1)
    response = client.patch(
        "/api/v1/departments/1",
        headers=auth_header(admin_user),
        json={},
    )
    assert response.status_code == 422


def test_update_department_clear_field_with_null(
    client, auth_header, admin_user, db
):
    """Gửi null cho field nullable -> giá trị bị xoá."""
    _seed_departments(db, count=1)
    headers = auth_header(admin_user)

    response = client.patch(
        "/api/v1/departments/1",
        headers=headers,
        json={"location": None},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["location"] is None


def test_update_department_not_found(client, auth_header, admin_user):
    """ID không tồn tại -> 404."""
    response = client.patch(
        "/api/v1/departments/99999",
        headers=auth_header(admin_user),
        json={"name": "không tồn tại"},
    )
    assert response.status_code == 404
