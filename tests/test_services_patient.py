"""Unit test cho PatientService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.errors import NotFoundException
from app.services.patient_service import PatientService


def _svc(**kwargs):
    """Tạo service với mock repo (mặc định)."""
    patient_repo = kwargs.get("patient_repo", MagicMock())
    return PatientService(patient_repository=patient_repo), patient_repo


# ==========================================================================
# count_patients
# ==========================================================================

class TestCountPatients:
    def test_count_patients_returns_total(self):
        """Test count_patients gọi repo.count() và trả về kết quả."""
        svc, repo = _svc()
        repo.count.return_value = 42
        result = svc.count_patients()
        repo.count.assert_called_once()
        assert result == 42

    def test_count_patients_zero(self):
        """Test count_patients khi không có bệnh nhân."""
        svc, repo = _svc()
        repo.count.return_value = 0
        result = svc.count_patients()
        assert result == 0


# ==========================================================================
# list_patients
# ==========================================================================

class TestListPatients:
    def test_calls_paginate(self):
        """Test list_patients gọi repo.paginate() với đúng tham số."""
        svc, repo = _svc()
        patient1 = MagicMock()
        patient2 = MagicMock()
        repo.paginate.return_value = ([patient1, patient2], 10)
        items, total = svc.list_patients(page=1, size=20)
        repo.paginate.assert_called_once_with(1, 20)
        assert len(items) == 2
        assert total == 10

    def test_list_patients_empty(self):
        """Test list_patients khi không có bệnh nhân."""
        svc, repo = _svc()
        repo.paginate.return_value = ([], 0)
        items, total = svc.list_patients(page=1, size=20)
        assert items == []
        assert total == 0


# ==========================================================================
# get_patient
# ==========================================================================

class TestGetPatient:
    def test_get_patient_found(self):
        """Test get_patient trả về bệnh nhân khi tìm thấy."""
        svc, repo = _svc()
        patient = MagicMock()
        patient.id = 1
        repo.find_by_id.return_value = patient
        result = svc.get_patient(1)
        repo.find_by_id.assert_called_once_with(1)
        assert result.id == 1

    def test_get_patient_not_found(self):
        """Test get_patient raise NotFoundException khi không tìm thấy."""
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_patient(999)


# ==========================================================================
# create_patient
# ==========================================================================

class TestCreatePatient:
    def test_create_patient_minimal(self):
        """Test tạo bệnh nhân với thông tin tối thiểu."""
        svc, repo = _svc()
        result = svc.create_patient(full_name="Nguyễn Văn A")
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.full_name == "Nguyễn Văn A"

    def test_create_patient_full_info(self):
        """Test tạo bệnh nhân với thông tin đầy đủ."""
        svc, repo = _svc()
        result = svc.create_patient(
            full_name="Trần Thị B",
            date_of_birth="1995-05-20",
            gender="female",
            phone="0987654321",
            email="patient@example.com",
            address="123 Main St",
        )
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.full_name == "Trần Thị B"
        assert result.gender == "female"

    def test_create_patient_invalid_date_format(self):
        """Test tạo bệnh nhân với date format sai."""
        svc, repo = _svc()
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc.create_patient(full_name="Test", date_of_birth="invalid-date")


# ==========================================================================
# update_patient
# ==========================================================================

class TestUpdatePatient:
    def test_update_patient_partial(self):
        """Test cập nhật bệnh nhân (chỉ một số trường)."""
        svc, repo = _svc()
        patient = MagicMock()
        patient.full_name = "Old Name"
        patient.phone = "0111111111"
        repo.find_by_id.return_value = patient
        result = svc.update_patient(1, full_name="New Name")
        assert result.full_name == "New Name"
        # Phone không thay đổi vì không truyền
        assert result.phone == "0111111111"
        repo.commit.assert_called_once()

    def test_update_patient_not_found(self):
        """Test cập nhật bệnh nhân không tồn tại."""
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_patient(999, full_name="New Name")

    def test_update_patient_invalid_date(self):
        """Test cập nhật bệnh nhân với date format sai."""
        svc, repo = _svc()
        patient = MagicMock()
        repo.find_by_id.return_value = patient
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc.update_patient(1, date_of_birth="bad-date")
