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
