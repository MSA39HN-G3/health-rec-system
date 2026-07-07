"""Unit tests for PatientService — covers all business logic methods."""
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

    def test_update_patient_all_fields(self):
        """Test cập nhật tất cả các trường của bệnh nhân."""
        svc, repo = _svc()
        patient = MagicMock()
        patient.full_name = "Old Name"
        patient.date_of_birth = None
        patient.gender = None
        patient.phone = None
        patient.email = None
        patient.address = None
        repo.find_by_id.return_value = patient
        
        result = svc.update_patient(
            1,
            full_name="New Name",
            date_of_birth="1990-01-01",
            gender="male",
            phone="0123456789",
            email="new@example.com",
            address="New Address",
        )
        
        assert result.full_name == "New Name"
        assert result.gender == "male"
        assert result.phone == "0123456789"
        assert result.email == "new@example.com"
        assert result.address == "New Address"
        repo.commit.assert_called_once()

    def test_update_patient_only_phone(self):
        """Test cập nhật chỉ phone field."""
        svc, repo = _svc()
        patient = MagicMock()
        patient.full_name = "Same Name"
        patient.phone = "0111111111"
        repo.find_by_id.return_value = patient
        
        result = svc.update_patient(1, phone="0987654321")
        assert result.phone == "0987654321"
        # Other fields unchanged
        assert result.full_name == "Same Name"
        repo.commit.assert_called_once()

    def test_update_patient_date_to_none(self):
        """Test cập nhật date_of_birth thành None từ giá trị cũ."""
        svc, repo = _svc()
        patient = MagicMock()
        patient.full_name = "Test"
        patient.date_of_birth = "1990-01-01"
        repo.find_by_id.return_value = patient
        
        # Passing date_of_birth=None should not update (None is treated as "not provided")
        result = svc.update_patient(1, date_of_birth=None)
        # date_of_birth should remain unchanged since None means "not provided"
        assert result.date_of_birth == "1990-01-01"


# ==========================================================================
# _parse_date (private method)
# ==========================================================================

class TestParseDate:
    def test_parse_date_valid_iso_string(self):
        """Test _parse_date với ISO format string hợp lệ."""
        svc, _ = _svc()
        result = svc._parse_date("1990-05-20")
        assert result.year == 1990
        assert result.month == 5
        assert result.day == 20

    def test_parse_date_none(self):
        """Test _parse_date với None."""
        svc, _ = _svc()
        result = svc._parse_date(None)
        assert result is None

    def test_parse_date_invalid_string_format(self):
        """Test _parse_date với format string không hợp lệ."""
        svc, _ = _svc()
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc._parse_date("20-05-1990")  # Wrong format

    def test_parse_date_invalid_type(self):
        """Test _parse_date với type không phải string."""
        svc, _ = _svc()
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc._parse_date(12345)  # Integer instead of string

    def test_parse_date_empty_string(self):
        """Test _parse_date với empty string."""
        svc, _ = _svc()
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc._parse_date("")

    def test_parse_date_leap_year(self):
        """Test _parse_date với leap year date."""
        svc, _ = _svc()
        result = svc._parse_date("2000-02-29")
        assert result.year == 2000
        assert result.month == 2
        assert result.day == 29

    def test_parse_date_invalid_day(self):
        """Test _parse_date với ngày không tồn tại."""
        svc, _ = _svc()
        from app.errors import BadRequestException

        with pytest.raises(BadRequestException):
            svc._parse_date("2021-02-30")  # Feb 30 doesn't exist


# ==========================================================================
# create_patient variations
# ==========================================================================

class TestCreatePatientVariations:
    def test_create_patient_with_date_only(self):
        """Test tạo bệnh nhân với date_of_birth nhưng không có trường khác."""
        svc, repo = _svc()
        result = svc.create_patient(
            full_name="Test Patient",
            date_of_birth="1995-01-15",
        )
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.full_name == "Test Patient"

    def test_create_patient_with_email_only(self):
        """Test tạo bệnh nhân với email nhưng không có trường khác."""
        svc, repo = _svc()
        result = svc.create_patient(
            full_name="Test Patient",
            email="test@example.com",
        )
        assert result.email == "test@example.com"
        repo.add.assert_called_once()

    def test_create_patient_with_address_only(self):
        """Test tạo bệnh nhân với address nhưng không có trường khác."""
        svc, repo = _svc()
        result = svc.create_patient(
            full_name="Test Patient",
            address="123 Street",
        )
        assert result.address == "123 Street"
        repo.add.assert_called_once()


# ==========================================================================
# list_patients variations
# ==========================================================================

class TestListPatientsVariations:
    def test_list_patients_page_2(self):
        """Test list_patients với page 2."""
        svc, repo = _svc()
        repo.paginate.return_value = ([], 50)
        items, total = svc.list_patients(page=2, size=20)
        repo.paginate.assert_called_once_with(2, 20)
        assert total == 50

    def test_list_patients_large_size(self):
        """Test list_patients với page size lớn."""
        svc, repo = _svc()
        patients = [MagicMock() for _ in range(100)]
        repo.paginate.return_value = (patients, 100)
        items, total = svc.list_patients(page=1, size=100)
        assert len(items) == 100
        assert total == 100

    def test_list_patients_single_item(self):
        """Test list_patients trả về 1 item."""
        svc, repo = _svc()
        patient = MagicMock()
        repo.paginate.return_value = ([patient], 1)
        items, total = svc.list_patients(page=1, size=20)
        assert len(items) == 1
        assert total == 1


# ==========================================================================
# count_patients variations
# ==========================================================================

class TestCountPatientsVariations:
    def test_count_patients_large_number(self):
        """Test count_patients với số lượng lớn."""
        svc, repo = _svc()
        repo.count.return_value = 10000
        result = svc.count_patients()
        assert result == 10000

    def test_count_patients_one(self):
        """Test count_patients khi có 1 bệnh nhân."""
        svc, repo = _svc()
        repo.count.return_value = 1
        result = svc.count_patients()
        assert result == 1

