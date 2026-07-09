"""Unit test cho DoctorService — phủ 3 nhánh phân quyền admin / dept_head."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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


class TestCreateDoctorValidation:
    """Test các nhánh validation của create_doctor."""

    def _svc(self, **kw):
        return _doctor_service(**kw)

    def test_create_doctor_duplicate_license(self):
        svc, dr, *_ = self._svc()
        # department OK nhưng license đã tồn tại.
        deptr = svc[2] if False else MagicMock()
        dr.find_by_license_number.return_value = MagicMock(id=42)
        dept_repo = MagicMock()
        dept_repo.find_by_id.return_value = MagicMock(id=1)
        svc = DoctorService(
            doctor_repository=dr,
            department_repository=dept_repo,
            role_repository=MagicMock(),
        )
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.create_doctor(
                actor=actor,
                data={
                    "full_name": "Nguyen Van A",
                    "department_id": 1,
                    "license_number": "VN-001",
                },
            )

    def test_create_doctor_department_not_found(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.departments.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.create_doctor(
                actor=actor,
                data={"full_name": "A", "department_id": 999},
            )


class TestUpdateDoctorValidation:
    """Test các nhánh validation của update_doctor."""

    def _setup(self):
        dr = MagicMock()
        deptr = MagicMock()
        deptr.find_by_id.return_value = MagicMock(id=1)
        svc = DoctorService(
            doctor_repository=dr,
            department_repository=deptr,
            role_repository=MagicMock(),
        )
        return svc, dr, deptr

    def test_update_doctor_not_found(self):
        svc, dr, _ = self._setup()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.update_doctor(
                actor=actor, doctor_id=999, data={"full_name": "X"}
            )

    def test_update_doctor_license_duplicate(self):
        svc, dr, _ = self._setup()
        doctor = MagicMock(license_number="OLD-1", department_id=1)
        dr.find_by_id.return_value = doctor
        dr.find_by_license_number.return_value = MagicMock(id=99)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"license_number": "NEW-1"},
            )

    def test_update_doctor_invalid_department(self):
        svc, dr, deptr = self._setup()
        doctor = MagicMock(license_number="X", department_id=1)
        dr.find_by_id.return_value = doctor
        deptr.find_by_id.return_value = None  # department không tồn tại
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"department_id": 999},
            )

    def test_update_doctor_change_avatar_invalidates_url(self):
        """Đổi avatar key -> url cache bị xoá."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            avatar_object_key="old/avatar.jpg",
            avatar_url="https://presigned/old",
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar"):
            svc.update_doctor(
                actor=actor,
                doctor_id=1,
                data={"avatar_object_key": "new/avatar.jpg"},
            )
        assert doctor.avatar_url is None

    def test_update_doctor_r2_cleanup(self):
        """Đổi avatar key -> phải gọi cleanup_old_avatar."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            avatar_object_key="old/a.jpg",
            avatar_url="cached",
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar") as cleanup:
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"avatar_object_key": "new/a.jpg"},
            )
        cleanup.assert_called_once_with("old/a.jpg", "new/a.jpg")


class TestDeleteDoctor:
    def test_delete_doctor_not_found(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.doctors.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.delete_doctor(actor=actor, doctor_id=999)

    def test_delete_doctor_calls_cleanup(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        doctor = MagicMock(avatar_object_key="old.jpg")
        svc.doctors.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar") as cleanup:
            svc.delete_doctor(actor=actor, doctor_id=1)
        svc.doctors.delete.assert_called_once_with(doctor)
        cleanup.assert_called_once_with("old.jpg", None)


class TestGetDoctorStatistics:
    def test_get_doctor_statistics_not_found(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
            statistics_repository=MagicMock(),
        )
        svc.doctors.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.get_doctor_statistics(actor=actor, doctor_id=999)

    def test_get_doctor_statistics_admin(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
            statistics_repository=MagicMock(),
        )
        svc.doctors.find_by_id.return_value = MagicMock(department_id=1)
        svc.statistics.find_or_create.return_value = MagicMock(id=1)
        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_doctor_statistics(actor=actor, doctor_id=1)
        assert result.id == 1


class TestGetExpiringLicenses:
    def test_denies_non_admin(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        actor = _user(has_roles=[Role.DOCTOR])
        with pytest.raises(ForbiddenException):
            svc.get_expiring_licenses(actor=actor, days=30)

    def test_returns_list_for_admin(self):
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.doctors.find_expiring_licenses.return_value = [MagicMock(), MagicMock()]
        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_expiring_licenses(actor=actor, days=10)
        assert len(result) == 2
        svc.doctors.find_expiring_licenses.assert_called_once_with(10)
