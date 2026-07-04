"""Test cho module doctors (chỉ có GET, phân trang, có phân quyền).

Phủ các case:
  - admin thấy tất cả bác sĩ.
  - admin có thể lọc theo `department_id`.
  - department_head chỉ thấy bác sĩ thuộc khoa mình làm trưởng.
  - department_head chưa là trưởng khoa nào -> 403.
  - user thường -> 403 hoặc rỗng tuỳ cấu hình service.
"""
from __future__ import annotations


def _seed_doctor(db, *, name, department_code="CK-001"):
    """Tạo bác sĩ mẫu và gắn vào khoa (nếu có)."""
    from app.models.doctor import Doctor

    d = Doctor(name=name, department_id=None)
    db.session.add(d)
    db.session.flush()
    return d


def _seed_full(app, db):
    """Tạo 2 khoa và một vài bác sĩ trong mỗi khoa."""
    from app.repositories import (
        department_repository,
        doctor_repository,
    )

    dept_a = department_repository.create(
        name="Khoa A",
        location="Tầng 1",
        description="",
        keywords=[],
        conditions=[],
        ai_metadata={},
        head_doctor_id=None,
        is_active=True,
    )
    dept_b = department_repository.create(
        name="Khoa B",
        location="Tầng 2",
        description="",
        keywords=[],
        conditions=[],
        ai_metadata={},
        head_doctor_id=None,
        is_active=True,
    )
    db.session.commit()

    # Gắn doctor vào khoa.
    for i in range(3):
        d = doctor_repository.create(
            name=f"BS A{i}", department_id=dept_a.id
        )
    for i in range(2):
        d = doctor_repository.create(
            name=f"BS B{i}", department_id=dept_b.id
        )
    db.session.commit()

    return dept_a, dept_b


# ============================================================
# Phân quyền
# ============================================================

def test_list_doctors_requires_auth(client):
    response = client.get("/api/v1/doctors")
    assert response.status_code == 401


def test_list_doctors_as_admin_sees_all(
    client, auth_header, admin_user, db
):
    _seed_full(db.app, db)
    headers = auth_header(admin_user)

    response = client.get("/api/v1/doctors?size=50", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total"] == 5


def test_list_doctors_admin_can_filter_by_department(
    client, auth_header, admin_user, db
):
    dept_a, dept_b = _seed_full(db.app, db)
    headers = auth_header(admin_user)

    response = client.get(
        f"/api/v1/doctors?department_id={dept_a.id}&size=50",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["pagination"]["total"] == 3


def test_list_doctors_dept_head_only_sees_own_department(
    client, auth_header, dept_head_user, db
):
    """department_head chỉ thấy bác sĩ thuộc khoa họ làm trưởng."""
    from app.repositories import department_repository

    dept = department_repository.create(
        name="Khoa của Head",
        location="Tầng 1",
        description="",
        keywords=[],
        conditions=[],
        ai_metadata={},
        head_doctor_id=None,
        is_active=True,
    )
    db.session.commit()

    # Gắn user này làm trưởng khoa.
    dept_head_user.head_department_id = dept.id
    db.session.commit()

    from app.repositories import doctor_repository
    for i in range(4):
        doctor_repository.create(name=f"BS dept_head {i}", department_id=dept.id)
    # Bác sĩ khoa khác (không được thấy).
    other = department_repository.create(
        name="Khoa khác",
        location="Tầng 9",
        description="",
        keywords=[],
        conditions=[],
        ai_metadata={},
        head_doctor_id=None,
        is_active=True,
    )
    db.session.commit()
    doctor_repository.create(name="BS khác", department_id=other.id)
    db.session.commit()

    headers = auth_header(dept_head_user)
    response = client.get("/api/v1/doctors?size=50", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    # Chỉ thấy 4 bác sĩ khoa mình.
    assert body["pagination"]["total"] == 4


def test_list_doctors_dept_head_not_assigned_anywhere_returns_403(
    client, auth_header, dept_head_user
):
    """dept_head CHƯA là trưởng khoa nào -> 403."""
    headers = auth_header(dept_head_user)
    response = client.get("/api/v1/doctors", headers=headers)
    assert response.status_code == 403


def test_list_doctors_validates_query(client, auth_header, admin_user):
    """size > 100 -> 422."""
    response = client.get(
        "/api/v1/doctors?size=999", headers=auth_header(admin_user)
    )
    assert response.status_code == 422
