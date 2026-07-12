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

    def test_staff_sees_all_when_no_filter(self):
        # Sau refactor 1a2b3c4d5e6f: staff quản lý tất cả bác sĩ, không còn
        # bị scope về khoa của "trưởng khoa". Staff thấy tất cả khoa, FE tự filter.
        svc, dr, deptr, _ = _doctor_service()
        dr.paginate.return_value = ([MagicMock(), MagicMock()], 2)
        actor = _user(has_roles=[Role.STAFF])

        items, total, scope = svc.list_doctors(actor=actor, page=1, size=10)
        dr.paginate.assert_called_once_with(1, 10, department_id=None)
        assert total == 2

    def test_staff_can_filter_by_department(self):
        # Sau refactor: staff có thể filter theo bất kỳ khoa nào FE yêu cầu.
        svc, dr, _, _ = _doctor_service()
        dr.paginate.return_value = ([MagicMock()], 1)
        actor = _user(has_roles=[Role.STAFF])

        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=42
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=42)

    def test_staff_other_department_allowed(self):
        # Sau refactor: staff không còn bị giới hạn khoa, được filter khoa khác.
        svc, dr, deptr, _ = _doctor_service()
        deptr.find_by_head_doctor_id.return_value = MagicMock(id=9)
        dr.paginate.return_value = ([], 0)
        actor = _user(has_roles=[Role.STAFF])

        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=99
        )
        # Không raise, filter theo đúng khoa client gửi.
        dr.paginate.assert_called_once_with(1, 10, department_id=99)

    def test_staff_passed_their_own_department(self):
        svc, dr, deptr, _ = _doctor_service()
        deptr.find_by_head_doctor_id.return_value = MagicMock(id=9)
        dr.paginate.return_value = ([], 0)
        actor = _user(has_roles=[Role.STAFF])

        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=9
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=9)
        assert total == 0

    def test_admin_and_staff_prioritises_admin(self):
        """User có cả admin + staff -> admin "thắng", được xem mọi khoa
        (không bị giới hạn bởi khoa nào cả)."""
        svc, dr, deptr, _ = _doctor_service()
        dr.paginate.return_value = ([MagicMock(), MagicMock(), MagicMock()], 3)
        actor = _user(has_roles=[Role.ADMIN, Role.STAFF])

        # Client filter department_id=42 (khoa khác) -> admin vẫn pass.
        items, total, scope = svc.list_doctors(
            actor=actor, page=1, size=10, department_id=42
        )
        dr.paginate.assert_called_once_with(1, 10, department_id=42)

        # Không filter -> thấy tất cả.
        items, total, scope = svc.list_doctors(actor=actor, page=1, size=10)
        dr.paginate.assert_called_with(1, 10, department_id=None)
        assert total == 3


class TestUpdatePermission:
    """Kiểm tra `_check_update_permission` với ưu tiên admin.

    Sau refactor 1a2b3c4d5e6f: staff quản lý tất cả bác sĩ, không còn bị
    scope theo khoa. Mọi test cũ về "dept_head_can_update_their_department"
    đã được đổi thành staff pass luôn.
    """

    def test_admin_can_update_any_doctor(self):
        svc, _, deptr, _ = _doctor_service()
        # Admin -> pass ngay.
        actor = _user(has_roles=[Role.ADMIN])
        any_doctor = MagicMock(department_id=999)  # khác khoa
        svc._check_update_permission(actor, any_doctor)

    def test_staff_can_update_any_doctor(self):
        # Sau refactor: staff pass luôn, không còn scope khoa.
        svc, _, _, _ = _doctor_service()
        actor = _user(has_roles=[Role.STAFF])
        any_doctor = MagicMock(department_id=999)
        svc._check_update_permission(actor, any_doctor)

    def test_admin_and_staff_prioritises_admin(self):
        """User vừa admin vừa staff -> admin thắng, sửa được bác sĩ
        thuộc khoa khác khoa mình đang trưởng."""
        svc, _, _, _ = _doctor_service()
        doctor = MagicMock(department_id=42)
        actor = _user(has_roles=[Role.ADMIN, Role.STAFF])

        # Pass ngay.
        svc._check_update_permission(actor, doctor)

    def test_no_role_raises_403(self):
        svc, *_ = _doctor_service()
        actor = _user(has_roles=[])
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

    def test_create_doctor_duplicate_email(self):
        """Tạo bác sĩ với email đã thuộc bác sĩ khác -> 422 doctor_duplicate_email."""
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.departments.find_by_id.return_value = MagicMock(id=1)
        svc.doctors.find_by_email.return_value = MagicMock(id=42)
        actor = _user(has_roles=[Role.ADMIN])

        from app.errors import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            svc.create_doctor(
                actor=actor,
                data={
                    "full_name": "B",
                    "department_id": 1,
                    "email": "dup@example.com",
                },
            )
        # i18n message_key phải trỏ tới errors.doctor_duplicate_email
        assert exc_info.value.message_key == "errors.doctor_duplicate_email"
        assert exc_info.value.details == {"email": "duplicate"}

    def test_create_doctor_email_case_insensitive(self):
        """Tìm email không phân biệt hoa thường — 'A@x.com' đụng 'a@x.com'."""
        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.departments.find_by_id.return_value = MagicMock(id=1)
        # repo được gọi với email đã chuẩn hoá (lowercase)
        svc.doctors.find_by_email.return_value = MagicMock(id=42)
        actor = _user(has_roles=[Role.ADMIN])

        from app.errors import ValidationException

        with pytest.raises(ValidationException):
            svc.create_doctor(
                actor=actor,
                data={
                    "full_name": "C",
                    "department_id": 1,
                    "email": "DUP@Example.COM",
                },
            )
        svc.doctors.find_by_email.assert_called_once_with("DUP@Example.COM")


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

    def test_update_doctor_avatar_idempotent(self):
        """Gửi cùng avatar key hiện tại -> _cleanup_old_avatar chạy nhưng
        không gọi storage.delete_object (idempotent — không xóa R2)."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            avatar_object_key="same/a.jpg",
            avatar_url="presigned-url",
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        # Patch delete_object ở module storage được import lazy trong _cleanup_old_avatar.
        # Dùng sys.modules để chặn thẳng hàm trong storage.
        with patch("app.services.storage.delete_object") as delete_obj:
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"avatar_object_key": "same/a.jpg"},
            )
        # Không gọi delete vì cùng key.
        delete_obj.assert_not_called()
        # avatar_url cũ vẫn giữ (không bị invalidate).
        assert doctor.avatar_url == "presigned-url"

    def test_update_doctor_clear_avatar(self):
        """PATCH avatar_object_key=null -> cleanup R2 + invalidate URL."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            avatar_object_key="old.jpg",
            avatar_url="cached-url",
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar") as cleanup:
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"avatar_object_key": None},
            )
        cleanup.assert_called_once_with("old.jpg", None)
        assert doctor.avatar_url is None

    def test_update_doctor_partial_keeps_missing_fields(self):
        """Field không gửi trong payload -> giữ nguyên giá trị gốc."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            full_name="Original",
            license_number="OLD",
            department_id=1,
            phone="0901234567",
            email="orig@example.com",
            title="BS",
            is_active=True,
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar"):
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"title": "TS"},  # chỉ đổi title
            )

        # Các field khác giữ nguyên.
        assert doctor.phone == "0901234567"
        assert doctor.email == "orig@example.com"
        assert doctor.license_number == "OLD"
        assert doctor.is_active is True
        # Field đổi đã được set.
        assert doctor.title == "TS"

    def test_update_doctor_duplicate_email(self):
        """Đổi email sang email của bác sĩ khác -> 422 doctor_duplicate_email."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            email="old@example.com",
        )
        dr.find_by_id.return_value = doctor
        dr.find_by_email.return_value = MagicMock(id=99)
        actor = _user(has_roles=[Role.ADMIN])

        from app.errors import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"email": "new@example.com"},
            )
        assert exc_info.value.message_key == "errors.doctor_duplicate_email"

    def test_update_doctor_email_same_value_skips_check(self):
        """Giữ nguyên email (gửi đúng email hiện tại) -> KHÔNG check duplicate."""
        svc, dr, _ = self._setup()
        doctor = MagicMock(
            license_number="X",
            department_id=1,
            email="same@example.com",
        )
        dr.find_by_id.return_value = doctor
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_avatar"):
            svc.update_doctor(
                actor=actor, doctor_id=1,
                data={"email": "same@example.com"},
            )
        dr.find_by_email.assert_not_called()

    def test_update_doctor_get_raises_doctor_not_found_key(self):
        """404 phải dùng i18n key 'errors.doctor_not_found', không phải key chung."""
        from app.errors import NotFoundException

        svc, dr, _ = self._setup()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException) as exc_info:
            svc.update_doctor(actor=actor, doctor_id=999, data={"full_name": "X"})
        assert exc_info.value.message_key == "errors.doctor_not_found"


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
        actor = _user(has_roles=[])  # không có role admin/staff -> bị denied
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


class TestGetDoctorNotFound:
    def test_get_doctor_uses_specific_message_key(self):
        """Khi không tìm thấy doctor -> dùng i18n key 'errors.doctor_not_found'."""
        from app.errors import NotFoundException

        svc = DoctorService(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
            role_repository=MagicMock(),
        )
        svc.doctors.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException) as exc_info:
            svc.get_doctor(actor=actor, doctor_id=999)
        assert exc_info.value.message_key == "errors.doctor_not_found"
