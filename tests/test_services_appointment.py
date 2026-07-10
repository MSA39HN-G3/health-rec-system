"""Unit test cho AppointmentService — phủ business logic quanh Appointment."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.errors import BadRequestException, NotFoundException
from app.services.appointment_service import AppointmentService


def _svc(**kwargs):
    repo = kwargs.get("appointment_repo", MagicMock())
    return AppointmentService(appointment_repository=repo), repo


# ==========================================================================
# list_appointments
# ==========================================================================

class TestListAppointments:
    def test_passes_pagination_and_filters(self):
        svc, repo = _svc()
        repo.paginate.return_value = (["a1", "a2"], 2)

        items, total = svc.list_appointments(
            2, 10,
            date_from="2026-07-01", date_to="2026-07-31",
            status="pending", doctor_id=5, department_id=3, patient_id=9,
        )

        repo.paginate.assert_called_once_with(
            2, 10,
            date_from=date(2026, 7, 1), date_to=date(2026, 7, 31),
            status="pending", doctor_id=5, department_id=3, patient_id=9,
        )
        assert items == ["a1", "a2"]
        assert total == 2

    def test_no_filters(self):
        svc, repo = _svc()
        repo.paginate.return_value = ([], 0)
        svc.list_appointments(1, 20)
        repo.paginate.assert_called_once_with(
            1, 20,
            date_from=None, date_to=None,
            status=None, doctor_id=None, department_id=None, patient_id=None,
        )

    def test_invalid_status_raises(self):
        svc, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.list_appointments(1, 20, status="bogus")

    def test_invalid_date_raises(self):
        svc, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.list_appointments(1, 20, date_from="not-a-date")


# ==========================================================================
# get_appointment
# ==========================================================================

class TestGetAppointment:
    def test_existing(self):
        svc, repo = _svc()
        apt = MagicMock()
        repo.find_by_id.return_value = apt
        assert svc.get_appointment(1) is apt
        repo.find_by_id.assert_called_once_with(1)

    def test_missing_raises_404(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_appointment(404)


# ==========================================================================
# get_status_history
# ==========================================================================

class TestGetStatusHistory:
    def test_returns_history_when_appointment_exists(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = MagicMock()
        repo.list_status_history.return_value = ["h1", "h2"]
        assert svc.get_status_history(7) == ["h1", "h2"]
        repo.list_status_history.assert_called_once_with(7)

    def test_missing_appointment_raises_404(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_status_history(404)


# ==========================================================================
# update_status
# ==========================================================================

class TestUpdateStatus:
    def test_updates_and_logs_history(self):
        svc, repo = _svc()
        apt = MagicMock(id=1, status="pending")
        repo.find_by_id.return_value = apt

        result = svc.update_status(1, "confirmed", changed_by=42, note="ok")

        assert result.status == "confirmed"
        repo.add_status_history.assert_called_once_with(
            1, old_status="pending", new_status="confirmed", changed_by=42, note="ok"
        )
        repo.commit.assert_called_once_with()

    def test_invalid_status_raises(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = MagicMock(status="pending")
        with pytest.raises(BadRequestException):
            svc.update_status(1, "bogus")

    def test_missing_appointment_raises_404(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_status(404, "confirmed")

    @pytest.mark.parametrize("terminal_status", ["completed", "cancelled"])
    def test_terminal_status_blocks_further_changes(self, terminal_status):
        svc, repo = _svc()
        repo.find_by_id.return_value = MagicMock(status=terminal_status)
        with pytest.raises(BadRequestException):
            svc.update_status(1, "confirmed")
        repo.commit.assert_not_called()


# ==========================================================================
# cancel_appointment
# ==========================================================================

class TestCancelAppointment:
    def test_cancels_and_logs_history(self):
        svc, repo = _svc()
        apt = MagicMock(id=3, status="pending")
        repo.find_by_id.return_value = apt

        result = svc.cancel_appointment(3, reason="Bệnh nhân bận", changed_by=7)

        assert result.status == "cancelled"
        assert result.cancel_reason == "Bệnh nhân bận"
        repo.add_status_history.assert_called_once_with(
            3, old_status="pending", new_status="cancelled", changed_by=7, note="Bệnh nhân bận"
        )
        repo.commit.assert_called_once_with()

    def test_missing_appointment_raises_404(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.cancel_appointment(404, reason="x")

    def test_already_finalized_raises(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = MagicMock(status="completed")
        with pytest.raises(BadRequestException):
            svc.cancel_appointment(1, reason="x")
        repo.commit.assert_not_called()
