"""Unit test cho DoctorStatisticsService.

Lưu ý: DoctorRatingService đã bị xóa cùng toàn bộ tính năng đánh giá ở
refactor 1c2d3e4f5a6b. Chỉ giữ test cho DoctorStatisticsService.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.common.roles import Role
from app.errors import ForbiddenException, NotFoundException
from app.services.doctor_statistics_service import DoctorStatisticsService


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
    s.cancelled_appointments = kwargs.get("cancelled_appointments", 5)
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


class TestDoctorStatisticsService:
    def _svc(self, **kw):
        sr = kw.get("stats_repo", MagicMock())
        dr = kw.get("doctor_repo", MagicMock())
        return DoctorStatisticsService(
            statistics_repository=sr,
            doctor_repository=dr,
        ), sr, dr

    # ---------- get_doctor_statistics ----------
    def test_get_doctor_statistics_success(self):
        svc, sr, dr = self._svc()
        dr.find_by_id.return_value = _doctor()
        sr.find_by_doctor_id.return_value = _statistics()

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_doctor_statistics(actor=actor, doctor_id=1)
        assert result is not None

    def test_get_doctor_statistics_doctor_not_found(self):
        svc, sr, dr = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.get_doctor_statistics(actor=actor, doctor_id=999)

    def test_get_doctor_statistics_forbidden(self):
        svc, sr, dr = self._svc()
        actor = _user(has_roles=[])  # không role nào
        with pytest.raises(ForbiddenException):
            svc.get_doctor_statistics(actor=actor, doctor_id=1)

    # ---------- get_top_rated_doctors (alias của get_most_appointments sau refactor) ----------
    def test_get_top_rated_doctors_success(self):
        svc, sr, _ = self._svc()
        # Sau refactor: get_top_rated_doctors fallback về get_most_appointments
        sr.get_most_appointments.return_value = [_statistics(), _statistics()]

        actor = _user(has_roles=[Role.ADMIN])
        items = svc.get_top_rated_doctors(actor=actor, limit=5)
        assert len(items) == 2

    # ---------- get_most_active_doctors ----------
    def test_get_most_active_doctors_success(self):
        svc, sr, _ = self._svc()
        sr.get_most_appointments.return_value = [_statistics()]
        actor = _user(has_roles=[Role.ADMIN])
        items = svc.get_most_active_doctors(actor=actor, limit=5)
        assert len(items) == 1

    # ---------- get_all_statistics ----------
    def test_get_all_statistics_admin_only(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[Role.STAFF])
        with pytest.raises(ForbiddenException):
            svc.get_all_statistics(actor=actor, page=1, size=20)

    # ---------- recalculate_doctor_statistics ----------
    def test_recalculate_statistics_success(self):
        svc, sr, dr = self._svc()
        dr.find_by_id.return_value = _doctor()
        sr.recalculate_for_doctor.return_value = _statistics()

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.recalculate_statistics(actor=actor, doctor_id=1)
        assert result is not None

    def test_recalculate_statistics_doctor_not_found(self):
        svc, _, dr = self._svc()
        dr.find_by_id.return_value = None
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.recalculate_statistics(actor=actor, doctor_id=999)


class TestDoctorStatisticsServiceAdditional:
    """Bổ sung test cho coverage."""

    def _svc(self, **kw):
        sr = kw.get("stats_repo", MagicMock())
        dr = kw.get("doctor_repo", MagicMock())
        return DoctorStatisticsService(
            statistics_repository=sr,
            doctor_repository=dr,
        ), sr, dr

    def test_permission_denied_for_unknown_role(self):
        svc, *_ = self._svc()
        actor = _user(has_roles=[])  # không có role admin/staff
        with pytest.raises(ForbiddenException):
            svc._check_permission(actor)

    def test_top_rated_allowed_for_staff(self):
        svc, sr, _ = self._svc()
        # service gọi get_most_appointments sau refactor
        sr.get_most_appointments.return_value = []
        actor = _user(has_roles=[Role.STAFF])
        items = svc.get_top_rated_doctors(actor=actor, limit=5)
        assert items == []

    def test_most_active_allowed_for_staff(self):
        svc, sr, _ = self._svc()
        sr.get_most_appointments.return_value = []
        actor = _user(has_roles=[Role.STAFF])
        items = svc.get_most_active_doctors(actor=actor, limit=5)
        assert items == []