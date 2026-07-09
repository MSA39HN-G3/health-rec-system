"""Unit test cho DoctorService — phủ 3 nhánh phân quyền admin / dept_head."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.common.roles import Role
from app.errors import ForbiddenException
from app.services.doctor_service import DoctorService


def _user(has_roles=()):
    u = MagicMock()
    u.id = 7
    u.has_role = lambda *names: bool(set(has_roles) & set(names))
    return u


def _doctor_service(**kw):
    dr = kw.get("doctor_repo", MagicMock())
    deptr = kw.get("department_repo", MagicMock())
    rr = kw.get("role_repo", MagicMock())
    return (
        DoctorService(
            doctor_repository=dr,
            department_repository=deptr,
            role_repository=rr,
        ),
        dr,
        deptr,
        rr,
    )


class TestListDoctors:
    def test_no_actor_raises_403(self):
        svc, *_ = _doctor_service()
        with pytest.raises(ForbiddenException):
            svc.list_doctors(actor=None, page=1, size=10)

    def test_plain_user_raises_403(self):
        svc, *_ = _doctor_service()
        actor = _user(has_roles=[])
        with pytest.raises(ForbiddenException):
            svc.list_doctors(actor=actor, page=1, size=10)

    def test_admin_sees_all_when_no_filter(self):
        svc, dr, _, _ = _doctor_service()
        dr.paginate.return_value = ([MagicMock(), MagicMock()], 2)
        actor = _user(has_roles=[Role.ADMIN])

        items, total, scope = svc.list_doctors(actor=actor, page=1, size=10)
        dr.paginate.assert_called_once_with(1, 10, department_id=None)
        assert total == 2
        assert scope == {"type": "all", "department_id": None, "label": "Tất cả khoa"}

    def test_admin_can_filter_by_department(self):
        svc, dr, _, _ = _doctor_service()
        dr.paginate.return_value = ([MagicMock()], 1)
        actor = _user(has_roles=[Role.ADMIN])

        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=42
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=42)
        assert scope == {
            "type": "department",
            "department_id": 42,
            "label": "Khoa #42",
        }

    def test_dept_head_with_department(self):
        svc, dr, deptr, _ = _doctor_service()
        dept = MagicMock()
        dept.id = 9
        dept.name = "Khoa A"
        deptr.find_by_head_doctor_id.return_value = dept
        # Service cũng gọi find_by_id(9) để lấy name cho scope label.
        deptr.find_by_id.return_value = dept
        dr.paginate.return_value = ([MagicMock()], 1)

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=9)
        assert scope == {
            "type": "department",
            "department_id": 9,
            "label": "Khoa A",
        }

    def test_dept_head_without_department_raises_403(self):
        svc, _, deptr, _ = _doctor_service()
        deptr.find_by_head_doctor_id.return_value = None
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc.list_doctors(actor=actor, page=1, size=10)

    def test_dept_head_other_department_raises_403(self):
        svc, _, deptr, _ = _doctor_service()
        dept = MagicMock()
        dept.id = 9
        deptr.find_by_head_doctor_id.return_value = dept
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc.list_doctors(
                actor=actor, page=1, size=10, department_id=99
            )

    def test_dept_head_passed_their_own_department(self):
        svc, dr, deptr, _ = _doctor_service()
        dept = MagicMock()
        dept.id = 9
        deptr.find_by_head_doctor_id.return_value = dept
        dr.paginate.return_value = ([], 0)
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=9
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=9)
        assert total == 0

    def test_admin_and_dept_head_prioritises_admin(self):
        """User có cả admin + department_head -> admin "thắng", được
        xem mọi khoa (không bị giới hạn bởi khoa của dept_head)."""
        svc, dr, deptr, _ = _doctor_service()
        # dept_head của khoa 9 nhưng actor cũng có admin.
        my_dept = MagicMock(id=9)
        deptr.find_by_head_doctor_id.return_value = my_dept
        dr.paginate.return_value = ([MagicMock(), MagicMock(), MagicMock()], 3)
        actor = _user(has_roles=[Role.ADMIN, Role.DEPARTMENT_HEAD])

        # Client filter department_id=42 (khoa khác) -> admin vẫn pass.
        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=42
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=42)
        assert scope["type"] == "department"
        assert scope["department_id"] == 42

        # Không filter -> thấy tất cả.
        items, total, scope = svc.list_doctors(actor=actor, page=1, size=10)
        dr.paginate.assert_called_with(1, 10, department_id=None)
        assert scope["type"] == "all"
        assert total == 3


class TestUpdatePermission:
    """Kiểm tra `_check_update_permission` với ưu tiên admin."""

    def test_admin_can_update_any_doctor(self):
        svc, _, deptr, _ = _doctor_service()
        # Admin -> pass ngay, không cần truy vấn department_repo.
        actor = _user(has_roles=[Role.ADMIN])
        any_doctor = MagicMock(department_id=999)  # khác khoa
        svc._check_update_permission(actor, any_doctor)
        deptr.find_by_head_doctor_id.assert_not_called()

    def test_dept_head_can_update_their_department(self):
        svc, _, deptr, _ = _doctor_service()
        my_dept = MagicMock(id=9)
        deptr.find_by_head_doctor_id.return_value = my_dept
        doctor = MagicMock(department_id=9)
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        svc._check_update_permission(actor, doctor)  # pass
        deptr.find_by_head_doctor_id.assert_called_once_with(actor.id)

    def test_dept_head_cannot_update_other_department(self):
        svc, _, deptr, _ = _doctor_service()
        my_dept = MagicMock(id=9)
        deptr.find_by_head_doctor_id.return_value = my_dept
        doctor = MagicMock(department_id=42)  # khoa khác
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with pytest.raises(ForbiddenException):
            svc._check_update_permission(actor, doctor)

    def test_admin_and_dept_head_prioritises_admin(self):
        """User vừa admin vừa dept_head -> admin thắng, sửa được bác sĩ
        thuộc khoa khác khoa mình đang trưởng."""
        svc, _, deptr, _ = _doctor_service()
        my_dept = MagicMock(id=9)
        deptr.find_by_head_doctor_id.return_value = my_dept
        doctor = MagicMock(department_id=42)  # khác khoa mình
        actor = _user(has_roles=[Role.ADMIN, Role.DEPARTMENT_HEAD])

        # Pass ngay, KHONG gọi find_by_head_doctor_id.
        svc._check_update_permission(actor, doctor)
        deptr.find_by_head_doctor_id.assert_not_called()

    def test_no_role_raises_403(self):
        svc, *_ = _doctor_service()
        actor = _user(has_roles=[])
        doctor = MagicMock(department_id=1)
        with pytest.raises(ForbiddenException):
            svc._check_update_permission(actor, doctor)

    def test_dept_head_without_department_raises_403(self):
        svc, _, deptr, _ = _doctor_service()
        deptr.find_by_head_doctor_id.return_value = None
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        doctor = MagicMock(department_id=1)
        with pytest.raises(ForbiddenException):
            svc._check_update_permission(actor, doctor)
