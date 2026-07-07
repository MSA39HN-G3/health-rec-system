"""Unit test cho HealthRecordService — phủ toàn bộ business logic quanh health_record."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.errors import BadRequestException, NotFoundException
from app.services.health_record_service import HealthRecordService


def _svc(**kwargs):
    hr = kwargs.get("hr_repo", MagicMock())
    pr = kwargs.get("patient_repo", MagicMock())
    dr = kwargs.get("doctor_repo", MagicMock())
    deptr = kwargs.get("department_repo", MagicMock())
    return (
        HealthRecordService(
            health_record_repository=hr,
            patient_repository=pr,
            doctor_repository=dr,
            department_repository=deptr,
        ),
        hr,
        pr,
        dr,
        deptr,
    )


# ==========================================================================
# list_records
# ==========================================================================

class TestListRecords:
    def test_patient_exists_passes_to_repo(self):
        svc, hr, pr, _, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        hr.paginate_by_patient.return_value = (["r1"], 1)

        items, total = svc.list_records(patient_id=7, page=1, size=10)
        pr.find_by_id.assert_called_once_with(7)
        hr.paginate_by_patient.assert_called_once_with(1, 10, 7)
        assert items == ["r1"]
        assert total == 1

    def test_patient_missing_raises(self):
        svc, _, pr, _, _ = _svc()
        pr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.list_records(patient_id=404, page=1, size=10)


# ==========================================================================
# get_record
# ==========================================================================

class TestGetRecord:
    def test_existing(self):
        svc, hr, _, _, _ = _svc()
        record = MagicMock()
        hr.find_by_patient_and_id.return_value = record
        assert svc.get_record(patient_id=1, record_id=2) is record
        hr.find_by_patient_and_id.assert_called_once_with(1, 2)

    def test_missing_raises(self):
        svc, hr, _, _, _ = _svc()
        hr.find_by_patient_and_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_record(patient_id=1, record_id=2)


# ==========================================================================
# create_record
# ==========================================================================

class TestCreateRecord:
    def test_minimal(self):
        svc, hr, pr, _, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        result = svc.create_record(patient_id=1, title="Khám định kỳ")
        hr.add.assert_called_once()
        hr.commit.assert_called_once()
        assert result.title == "Khám định kỳ"

    def test_patient_missing_raises(self):
        svc, _, pr, _, _ = _svc()
        pr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_record(patient_id=99, title="x")

    def test_doctor_missing_raises(self):
        svc, _, pr, dr, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        dr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_record(patient_id=1, title="x", doctor_id=42)

    def test_doctor_found(self):
        svc, hr, pr, dr, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        dr.find_by_id.return_value = MagicMock()
        svc.create_record(patient_id=1, title="x", doctor_id=42)
        dr.find_by_id.assert_called_once_with(42)
        hr.commit.assert_called_once()

    def test_department_missing_raises(self):
        svc, _, pr, _, deptr = _svc()
        pr.find_by_id.return_value = MagicMock()
        deptr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_record(patient_id=1, title="x", department_id=10)

    def test_department_found(self):
        svc, hr, pr, _, deptr = _svc()
        pr.find_by_id.return_value = MagicMock()
        deptr.find_by_id.return_value = MagicMock()
        svc.create_record(patient_id=1, title="x", department_id=10)
        deptr.find_by_id.assert_called_once_with(10)

    def test_all_fields_with_dates(self):
        svc, hr, pr, dr, deptr = _svc()
        pr.find_by_id.return_value = MagicMock()
        dr.find_by_id.return_value = MagicMock()
        deptr.find_by_id.return_value = MagicMock()
        result = svc.create_record(
            patient_id=1,
            title="x",
            visit_date="2025-06-15T10:30:00",
            doctor_id=42,
            department_id=10,
            notes="n",
            diagnosis="d",
            treatment="t",
        )
        hr.add.assert_called_once()
        hr.commit.assert_called_once()
        assert result.title == "x"

    def test_invalid_visit_date_string(self):
        svc, _, pr, _, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        with pytest.raises(BadRequestException):
            svc.create_record(patient_id=1, title="x", visit_date="không-phải-giờ")

    def test_non_string_visit_date(self):
        svc, _, pr, _, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        with pytest.raises(BadRequestException):
            svc.create_record(patient_id=1, title="x", visit_date=42)

    def test_none_visit_date_allowed(self):
        svc, hr, pr, _, _ = _svc()
        pr.find_by_id.return_value = MagicMock()
        svc.create_record(patient_id=1, title="x", visit_date=None)
        hr.commit.assert_called_once()


# ==========================================================================
# update_record
# ==========================================================================

class TestUpdateRecord:
    def _setup_existing(self, **kwargs):
        existing = MagicMock()
        existing.title = "Old"
        existing.notes = "Old"
        existing.diagnosis = "Old"
        existing.treatment = "Old"
        svc, hr, pr, dr, deptr = _svc(**kwargs)
        hr.find_by_patient_and_id.return_value = existing
        return svc, hr, pr, dr, deptr, existing

    def test_updates_all_fields(self):
        svc, hr, *_ , existing = self._setup_existing()
        svc.update_record(
            patient_id=1,
            record_id=2,
            title="New",
            visit_date="2025-01-01T08:00:00",
            notes="new-n",
            diagnosis="new-d",
            treatment="new-t",
        )
        assert existing.title == "New"
        hr.commit.assert_called_once()

    def test_record_not_found(self):
        svc, hr, *_ = _svc()
        hr.find_by_patient_and_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_record(1, 2, title="x")

    def test_doctor_id_missing_raises(self):
        svc, hr, _, dr, _ = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        dr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_record(1, 2, doctor_id=42)

    def test_doctor_id_zero_skips_check(self):
        """doctor_id=0 (hoặc falsy khác None) sẽ không gọi find_by_id."""
        svc, hr, _, dr, _ = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        svc.update_record(1, 2, doctor_id=0)
        dr.find_by_id.assert_not_called()
        hr.commit.assert_called_once()

    def test_department_id_missing_raises(self):
        svc, hr, _, _, deptr = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        deptr.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_record(1, 2, department_id=10)

    def test_department_id_zero_skips_check(self):
        svc, hr, _, _, deptr = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        svc.update_record(1, 2, department_id=0)
        deptr.find_by_id.assert_not_called()
        hr.commit.assert_called_once()

    def test_invalid_visit_date_string(self):
        svc, hr, *_ = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        with pytest.raises(BadRequestException):
            svc.update_record(1, 2, visit_date="không-phải-giờ")

    def test_non_string_visit_date(self):
        svc, hr, *_ = _svc()
        hr.find_by_patient_and_id.return_value = MagicMock()
        with pytest.raises(BadRequestException):
            svc.update_record(1, 2, visit_date=[])

    def test_no_fields_still_calls_commit(self):
        svc, hr, *_ = self._setup_existing()
        svc.update_record(patient_id=1, record_id=2)
        hr.commit.assert_called_once()
