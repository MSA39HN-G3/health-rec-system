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
