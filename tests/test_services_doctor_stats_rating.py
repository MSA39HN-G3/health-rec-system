"""Unit test cho DoctorStatisticsService và DoctorRatingService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.common.roles import Role
from app.errors import ForbiddenException, NotFoundException
from app.services.doctor_statistics_service import DoctorStatisticsService
from app.services.doctor_rating_service import DoctorRatingService


def _user(has_roles=()):
    u = MagicMock()
    u.id = 7
    u.has_role = lambda *names: bool(set(has_roles) & set(names))
    return u


def _doctor(id=1, department_id=1):
    d = MagicMock()
    d.id = id
    d.department_id = department_id
    return d


def _statistics(id=1, doctor_id=1, **kwargs):
    s = MagicMock()
    s.id = id
    s.doctor_id = doctor_id
    s.total_appointments = kwargs.get("total_appointments", 100)
    s.completed_appointments = kwargs.get("completed_appointments", 90)
    s.average_rating = kwargs.get("average_rating", 4.5)
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def _rating(id=1, doctor_id=1, patient_id=1, rating=5):
    r = MagicMock()
    r.id = id
    r.doctor_id = doctor_id
    r.patient_id = patient_id
    r.rating = rating
    r.comment = "Great doctor!"
    return r


class TestDoctorStatisticsService:
    def _svc(self, **kw):
        sr = kw.get("stats_repo", MagicMock())
        dr = kw.get("doctor_repo", MagicMock())
        return DoctorStatisticsService(
            statistics_repository=sr,
            doctor_repository=dr,
        ), sr, dr

    def test_get_doctor_statistics(self):
        svc, sr, dr = self._svc()
        doctor = _doctor(id=1)
        stats = _statistics(id=1, doctor_id=1)
        dr.find_by_id.return_value = doctor
        sr.find_or_create.return_value = stats

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_doctor_statistics(actor=actor, doctor_id=1)

        assert result.id == 1
        assert result.total_appointments == 100

    def test_get_nonexistent_doctor_statistics_raises(self):
        svc, sr, dr = self._svc()
        dr.find_by_id.return_value = None

        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.get_doctor_statistics(actor=actor, doctor_id=999)

    def test_recalculate_statistics(self):
        svc, sr, dr = self._svc()
        doctor = _doctor(id=1)
        stats = _statistics(id=1, doctor_id=1)
        dr.find_by_id.return_value = doctor
        sr.recalculate_for_doctor.return_value = stats

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.recalculate_statistics(actor=actor, doctor_id=1)

        sr.recalculate_for_doctor.assert_called_once_with(1)
        assert result.id == 1

    def test_recalculate_requires_admin(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with pytest.raises(ForbiddenException):
            svc.recalculate_statistics(actor=actor, doctor_id=1)

    def test_dept_head_get_own_department_statistics(self):
        svc, sr, dr = self._svc()
        doctor = _doctor(id=1, department_id=9)
        stats = _statistics(id=1, doctor_id=1)
        dr.find_by_id.return_value = doctor
        sr.find_or_create.return_value = stats

        my_dept = MagicMock(id=9)
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with patch(
            "app.repositories.department_repository.DepartmentRepository"
        ) as dept_mock:
            dept_mock.return_value.find_by_head_doctor_id.return_value = my_dept
            result = svc.get_doctor_statistics(actor=actor, doctor_id=1)

        assert result.id == 1

    def test_dept_head_denied_other_department(self):
        svc, sr, dr = self._svc()
        doctor = _doctor(id=1, department_id=42)
        dr.find_by_id.return_value = doctor

        my_dept = MagicMock(id=9)
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with patch(
            "app.repositories.department_repository.DepartmentRepository"
        ) as dept_mock:
            dept_mock.return_value.find_by_head_doctor_id.return_value = my_dept
            with pytest.raises(ForbiddenException):
                svc.get_doctor_statistics(actor=actor, doctor_id=1)

    def test_dept_head_without_head_allow_access(self):
        """dept_head chưa được gán làm trưởng khoa nào -> bỏ check khoa,
        vẫn pass (giữ tương thích ngược: không raise)."""
        svc, sr, dr = self._svc()
        doctor = _doctor(id=1, department_id=42)
        stats = _statistics(id=1, doctor_id=1)
        dr.find_by_id.return_value = doctor
        sr.find_or_create.return_value = stats

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with patch(
            "app.repositories.department_repository.DepartmentRepository"
        ) as dept_mock:
            dept_mock.return_value.find_by_head_doctor_id.return_value = None
            # Vẫn pass vì chỉ raise khi my_dept truthy và khác khoa doctor.
            result = svc.get_doctor_statistics(actor=actor, doctor_id=1)
            assert result.id == 1

    def test_get_top_rated_doctors(self):
        svc, sr, _ = self._svc()
        top_stats = [_statistics(id=1), _statistics(id=2)]
        sr.get_top_rated.return_value = top_stats

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_top_rated_doctors(actor=actor, limit=10)

        sr.get_top_rated.assert_called_once_with(10)
        assert len(result) == 2


class TestDoctorRatingService:
    def _svc(self, **kw):
        rr = kw.get("rating_repo", MagicMock())
        dr = kw.get("doctor_repo", MagicMock())
        pr = kw.get("patient_repo", MagicMock())
        sr = kw.get("stats_repo", MagicMock())
        return DoctorRatingService(
            rating_repository=rr,
            doctor_repository=dr,
            patient_repository=pr,
            statistics_repository=sr,
        ), rr, dr, pr, sr

    def test_create_rating(self):
        svc, rr, dr, pr, sr = self._svc()
        doctor = _doctor(id=1)
        patient = MagicMock()
        patient.id = 1
        patient.user_id = 7

        dr.find_by_id.return_value = doctor
        pr.find_by_id.return_value = patient
        rr.has_rated_appointment.return_value = False
        rr.add.return_value = _rating(id=1, rating=5)
        sr.recalculate_for_doctor.return_value = MagicMock()

        actor = _user(has_roles=[Role.PATIENT])
        data = {
            "doctor_id": 1,
            "patient_id": 1,
            "rating": 5,
            "comment": "Excellent!",
        }

        result = svc.create_rating(actor=actor, data=data)

        rr.add.assert_called_once()
        sr.recalculate_for_doctor.assert_called_once_with(1)

    def test_create_rating_invalid_value(self):
        svc, rr, dr, pr, _ = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        pr.find_by_id.return_value = MagicMock()

        actor = _user(has_roles=[Role.PATIENT])

        # Rating too low
        with pytest.raises(Exception):
            svc.create_rating(actor=actor, data={
                "doctor_id": 1, "patient_id": 1, "rating": 0
            })

        # Rating too high
        with pytest.raises(Exception):
            svc.create_rating(actor=actor, data={
                "doctor_id": 1, "patient_id": 1, "rating": 6
            })

    def test_get_doctor_ratings(self):
        svc, rr, dr, *_ = self._svc()
        ratings = [_rating(id=1), _rating(id=2)]
        dr.find_by_id.return_value = _doctor(id=1)
        rr.find_by_doctor_id.return_value = (ratings, 2)

        actor = _user(has_roles=[Role.PATIENT])
        items, total = svc.get_doctor_ratings(actor=actor, doctor_id=1, page=1, size=20)

        assert len(items) == 2
        assert total == 2

    def test_get_rating_distribution(self):
        svc, rr, dr, *_ = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        rr.get_rating_distribution.return_value = {1: 0, 2: 1, 3: 2, 4: 10, 5: 7}

        actor = _user(has_roles=[Role.PATIENT])
        result = svc.get_rating_distribution(actor=actor, doctor_id=1)

        assert result[5] == 7  # 5 stars: 7 ratings

    def test_delete_rating_requires_admin(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.PATIENT])

        with pytest.raises(ForbiddenException):
            svc.delete_rating(actor=actor, rating_id=1)

    def test_admin_can_delete_rating(self):
        svc, rr, dr, *_ = self._svc()
        rating = _rating(id=1, doctor_id=1)
        rr.find_by_id.return_value = rating

        actor = _user(has_roles=[Role.ADMIN])
        with patch.object(svc.statistics, "recalculate_for_doctor"):
            svc.delete_rating(actor=actor, rating_id=1)

        rr.delete.assert_called_once()

    # === Phân quyền bệnh nhân ===

    def test_check_patient_permission_denies_no_actor(self):
        svc, *_ = self._svc()
        with pytest.raises(ForbiddenException):
            svc._check_patient_permission(None, patient_id=1)

    def test_check_patient_permission_allows_admin(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.ADMIN])
        # Admin pass ngay, không cần patient.
        assert svc._check_patient_permission(actor, patient_id=1) is True

    def test_check_patient_permission_allows_self_patient(self):
        svc, _, _, pr, _ = self._svc()
        # Patient.user_id == actor.id
        patient = MagicMock(id=5, user_id=7)
        pr.find_by_id.return_value = patient
        actor = _user(has_roles=[Role.PATIENT])
        assert svc._check_patient_permission(actor, patient_id=5) is True

    def test_check_patient_permission_denies_other_patient(self):
        svc, _, _, pr, _ = self._svc()
        # Patient.user_id != actor.id -> 403.
        patient = MagicMock(id=5, user_id=99)
        pr.find_by_id.return_value = patient
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(ForbiddenException):
            svc._check_patient_permission(actor, patient_id=5)

    def test_check_patient_permission_denies_plain_user(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[])
        with pytest.raises(ForbiddenException):
            svc._check_patient_permission(actor, patient_id=1)

    def test_check_patient_permission_when_patient_not_found(self):
        """PATIENT role nhưng không tìm thấy patient_id -> 403."""
        svc, _, _, pr, _ = self._svc()
        pr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(ForbiddenException):
            svc._check_patient_permission(actor, patient_id=999)

    def test_check_patient_permission_allows_staff(self):
        """STAFF được tạo đánh giá hộ bệnh nhân."""
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.STAFF])
        assert svc._check_patient_permission(actor, patient_id=1) is True

    # === Create rating: các nhánh lỗi ===

    def test_create_rating_when_doctor_not_found(self):
        svc, rr, dr, *_ = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.create_rating(
                actor=actor,
                data={"doctor_id": 999, "patient_id": 1, "rating": 5},
            )

    def test_create_rating_when_patient_not_found(self):
        svc, _, dr, pr, _ = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        pr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.create_rating(
                actor=actor,
                data={"doctor_id": 1, "patient_id": 999, "rating": 4},
            )

    def test_create_rating_invalid_rating_type(self):
        """rating là string thay vì int."""
        svc, _, dr, pr, _ = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        pr.find_by_id.return_value = MagicMock()
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.create_rating(
                actor=actor,
                data={"doctor_id": 1, "patient_id": 1, "rating": "high"},
            )

    def test_create_rating_with_duplicate_appointment(self):
        """Đã rate appointment này rồi -> conflict."""
        svc, rr, dr, pr, sr = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        pr.find_by_id.return_value = MagicMock()
        rr.has_rated_appointment.return_value = True
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.create_rating(
                actor=actor,
                data={
                    "doctor_id": 1, "patient_id": 1,
                    "appointment_id": 99, "rating": 5,
                },
            )

    def test_create_rating_without_appointment_skips_dup_check(self):
        """Khi không truyền appointment_id thì không check has_rated."""
        svc, rr, dr, pr, sr = self._svc()
        dr.find_by_id.return_value = _doctor(id=1)
        pr.find_by_id.return_value = MagicMock()
        rr.add.return_value = _rating(id=1)
        sr.recalculate_for_doctor.return_value = MagicMock()

        actor = _user(has_roles=[Role.ADMIN])
        svc.create_rating(
            actor=actor,
            data={"doctor_id": 1, "patient_id": 1, "rating": 4},
        )
        rr.has_rated_appointment.assert_not_called()

    # === Get / Update / Delete ===

    def test_get_rating_success(self):
        svc, rr, *_ = self._svc()
        rating = _rating(id=42)
        rr.find_by_id.return_value = rating
        actor = _user(has_roles=[Role.PATIENT])
        result = svc.get_rating(actor=actor, rating_id=42)
        assert result.id == 42

    def test_get_rating_not_found(self):
        svc, rr, *_ = self._svc()
        rr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(NotFoundException):
            svc.get_rating(actor=actor, rating_id=999)

    def test_get_doctor_ratings_when_doctor_not_found(self):
        svc, _, dr, *_ = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(NotFoundException):
            svc.get_doctor_ratings(actor=actor, doctor_id=999)

    def test_delete_rating_when_not_found(self):
        svc, rr, *_ = self._svc()
        rr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.delete_rating(actor=actor, rating_id=999)

    # === Update rating ===

    def test_admin_can_update_any_rating(self):
        svc, rr, _, pr, sr = self._svc()
        rating = _rating(id=1, rating=3)
        rr.find_by_id.return_value = rating
        rr.update.return_value = rating
        sr.recalculate_for_doctor.return_value = MagicMock()

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.update_rating(
            actor=actor, rating_id=1, data={"rating": 5}
        )
        assert result.rating == 5
        rr.update.assert_called_once()
        sr.recalculate_for_doctor.assert_called_once_with(1)

    def test_owner_patient_can_update_own_rating(self):
        svc, rr, _, pr, sr = self._svc()
        rating = _rating(id=1, patient_id=5, rating=3)
        patient = MagicMock(id=5, user_id=7)
        pr.find_by_id.return_value = patient
        rr.find_by_id.return_value = rating
        rr.update.return_value = rating
        sr.recalculate_for_doctor.return_value = MagicMock()

        actor = _user(has_roles=[Role.PATIENT])
        result = svc.update_rating(
            actor=actor, rating_id=1, data={"comment": "Updated comment"}
        )
        assert result.comment == "Updated comment"

    def test_other_patient_cannot_update_rating(self):
        svc, rr, _, pr, _ = self._svc()
        rating = _rating(id=1, patient_id=5, rating=3)
        patient = MagicMock(id=5, user_id=99)  # không phải actor
        pr.find_by_id.return_value = patient
        rr.find_by_id.return_value = rating

        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(ForbiddenException):
            svc.update_rating(
                actor=actor, rating_id=1, data={"rating": 1}
            )

    def test_update_rating_not_found(self):
        svc, rr, *_ = self._svc()
        rr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.update_rating(
                actor=actor, rating_id=999, data={"rating": 5}
            )

    def test_update_rating_with_invalid_value(self):
        svc, rr, *_ = self._svc()
        rating = _rating(id=1)
        rr.find_by_id.return_value = rating

        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(Exception):
            svc.update_rating(
                actor=actor, rating_id=1, data={"rating": 99}
            )

    def test_update_rating_when_owner_patient_missing(self):
        """Rating tồn tại nhưng patient không tìm thấy -> 403."""
        svc, rr, _, pr, _ = self._svc()
        rr.find_by_id.return_value = _rating(id=1)
        pr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(ForbiddenException):
            svc.update_rating(
                actor=actor, rating_id=1, data={"comment": "x"}
            )

    # === get_patient_ratings ===

    def test_get_patient_ratings_admin(self):
        svc, rr, *_ = self._svc()
        rr.find_by_patient_id.return_value = [_rating(id=1), _rating(id=2)]
        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_patient_ratings(actor=actor, patient_id=1)
        assert len(result) == 2

    def test_get_patient_ratings_self(self):
        svc, rr, _, pr, _ = self._svc()
        patient = MagicMock(user_id=7)
        pr.find_by_id.return_value = patient
        rr.find_by_patient_id.return_value = [_rating(id=1)]
        actor = _user(has_roles=[Role.PATIENT])
        result = svc.get_patient_ratings(actor=actor, patient_id=1)
        assert len(result) == 1

    def test_get_patient_ratings_other_denied(self):
        svc, _, _, pr, _ = self._svc()
        patient = MagicMock(user_id=99)  # khác actor
        pr.find_by_id.return_value = patient
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(ForbiddenException):
            svc.get_patient_ratings(actor=actor, patient_id=1)

    def test_get_patient_ratings_no_actor(self):
        svc, *_ = self._svc()
        with pytest.raises(ForbiddenException):
            svc.get_patient_ratings(actor=None, patient_id=1)

    # === get_rating_distribution cho doctor không tồn tại ===

    def test_get_rating_distribution_doctor_not_found(self):
        svc, _, dr, *_ = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.PATIENT])
        with pytest.raises(NotFoundException):
            svc.get_rating_distribution(actor=actor, doctor_id=999)


class TestDoctorStatisticsServiceAdditional:
    """Test bổ sung cho DoctorStatisticsService để tăng coverage."""

    def _svc(self, **kw):
        sr = kw.get("stats_repo", MagicMock())
        dr = kw.get("doctor_repo", MagicMock())
        return DoctorStatisticsService(
            statistics_repository=sr,
            doctor_repository=dr,
        ), sr, dr

    def test_check_permission_denies_no_actor(self):
        svc, *_ = self._svc()
        with pytest.raises(ForbiddenException):
            svc._check_permission(None)

    def test_check_permission_denies_plain_user(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DOCTOR])
        with pytest.raises(ForbiddenException):
            svc._check_permission(actor)

    def test_check_permission_allows_admin(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.ADMIN])
        svc._check_permission(actor)  # pass

    def test_check_admin_only_denies_dept_head(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc._check_admin_only(actor)

    def test_recalculate_statistics_doctor_not_found(self):
        svc, _, dr = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.recalculate_statistics(actor=actor, doctor_id=999)

    def test_get_top_rated_requires_permission(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DOCTOR])
        with pytest.raises(ForbiddenException):
            svc.get_top_rated_doctors(actor=actor, limit=5)

    def test_get_most_active_doctors(self):
        svc, sr, _ = self._svc()
        sr.get_most_appointments.return_value = [_statistics(id=1), _statistics(id=2)]
        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_most_active_doctors(actor=actor, limit=5)
        sr.get_most_appointments.assert_called_once_with(5)
        assert len(result) == 2

    def test_get_most_active_doctors_requires_permission(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DOCTOR])
        with pytest.raises(ForbiddenException):
            svc.get_most_active_doctors(actor=actor, limit=5)

    def test_get_all_statistics_requires_admin(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        with pytest.raises(ForbiddenException):
            svc.get_all_statistics(actor=actor)
