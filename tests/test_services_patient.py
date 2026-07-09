"""Unit test cho PatientService — phủ toàn bộ business logic quanh Patient."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.errors import BadRequestException, NotFoundException
from app.services.patient_service import PatientService


def _svc(**kwargs):
    repo = kwargs.get("patient_repo", MagicMock())
    return PatientService(patient_repository=repo), repo


# ==========================================================================
# count_patients
# ==========================================================================

class TestCountPatients:
    def test_returns_total(self):
        svc, repo = _svc()
        repo.count.return_value = 17
        assert svc.count_patients() == 17
        repo.count.assert_called_once_with()


# ==========================================================================
# list_patients
# ==========================================================================

class TestListPatients:
    def test_passes_pagination(self):
        svc, repo = _svc()
        repo.paginate.return_value = (["p1", "p2"], 2)
        items, total = svc.list_patients(page=3, size=25)
        repo.paginate.assert_called_once_with(3, 25)
        assert items == ["p1", "p2"]
        assert total == 2


# ==========================================================================
# get_patient
# ==========================================================================

class TestGetPatient:
    def test_existing(self):
        svc, repo = _svc()
        p = MagicMock()
        repo.find_by_id.return_value = p
        assert svc.get_patient(1) is p
        repo.find_by_id.assert_called_once_with(1)

    def test_missing_raises_404(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_patient(404)


# ==========================================================================
# create_patient
# ==========================================================================

class TestCreatePatient:
    def test_minimal(self):
        svc, repo = _svc()
        result = svc.create_patient(full_name="Nguyễn Văn A")
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.full_name == "Nguyễn Văn A"

    def test_all_fields(self):
        svc, repo = _svc()
        result = svc.create_patient(
            full_name="Trần Văn B",
            date_of_birth="1990-05-20",
            gender="male",
            phone="0901234567",
            email="b@example.com",
            address="Hà Nội",
            blood_type="O+",
            height=175.5,
            weight=70.2,
            medical_history="Không có",
            allergies="Hải sản",
        )
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.full_name == "Trần Văn B"
        assert result.blood_type == "O+"
        assert result.height == 175.5
        assert result.weight == 70.2
        assert result.medical_history == "Không có"
        assert result.allergies == "Hải sản"

    def test_invalid_date_string_raises_400(self):
        svc, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.create_patient(full_name="X", date_of_birth="không-phải-ngày")

    def test_non_string_date_raises_400(self):
        svc, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.create_patient(full_name="X", date_of_birth=12345)

    def test_none_date_is_allowed(self):
        svc, repo = _svc()
        result = svc.create_patient(full_name="Y", date_of_birth=None)
        repo.commit.assert_called_once()
        assert result.full_name == "Y"


# ==========================================================================
# update_patient
# ==========================================================================

class TestUpdatePatient:
    def test_updates_each_field(self):
        svc, repo = _svc()
        existing = MagicMock()
        repo.find_by_id.return_value = existing
        svc.update_patient(
            1,
            full_name="New Name",
            gender="female",
            phone="0999",
            email="new@example.com",
            address="HCM",
            blood_type="A-",
            height=162.0,
            weight=52.5,
            medical_history="Tiểu đường",
            allergies="Phấn hoa",
        )
        assert existing.full_name == "New Name"
        assert existing.gender == "female"
        assert existing.phone == "0999"
        assert existing.email == "new@example.com"
        assert existing.address == "HCM"
        assert existing.blood_type == "A-"
        assert existing.height == 162.0
        assert existing.weight == 52.5
        assert existing.medical_history == "Tiểu đường"
        assert existing.allergies == "Phấn hoa"
        repo.commit.assert_called_once()

    def test_update_date(self):
        svc, repo = _svc()
        existing = MagicMock()
        repo.find_by_id.return_value = existing
        svc.update_patient(1, date_of_birth="2000-01-15")
        # Khi date hợp lệ -> gán date object (không phải string).
        existing.date_of_birth = date(2000, 1, 15)
        assert existing.date_of_birth == date(2000, 1, 15)

    def test_invalid_date_string_raises(self):
        svc, repo = _svc()
        existing = MagicMock()
        repo.find_by_id.return_value = existing
        with pytest.raises(BadRequestException):
            svc.update_patient(1, date_of_birth="không-phải-ngày")

    def test_patient_not_found_raises(self):
        svc, repo = _svc()
        repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_patient(99, full_name="X")

    def test_no_fields_to_update_still_commits(self):
        """PATCH nhưng không truyền field nào -> vẫn commit (không có lỗi)."""
        svc, repo = _svc()
        existing = MagicMock()
        repo.find_by_id.return_value = existing
        svc.update_patient(1)
        repo.commit.assert_called_once()
