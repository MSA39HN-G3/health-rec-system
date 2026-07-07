"""Unit tests for PatientRepository — covers all data access layer methods."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm.session import Session

from app.extensions import db
from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def repo(mock_session):
    """Create repository with mocked db.session."""
    repo = PatientRepository()
    repo.db = mock_session
    return repo


# ==========================================================================
# find_by_id
# ==========================================================================

class TestFindById:
    def test_find_by_id_found(self):
        """Test find_by_id returns patient when found."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            patient = MagicMock()
            mock_session.get.return_value = patient
            
            repo = PatientRepository()
            result = repo.find_by_id(1)
            
            mock_session.get.assert_called_once_with(Patient, 1)
            assert result == patient

    def test_find_by_id_not_found(self):
        """Test find_by_id returns None when patient not found."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            mock_session.get.return_value = None
            
            repo = PatientRepository()
            result = repo.find_by_id(999)
            
            assert result is None

    def test_find_by_id_with_different_ids(self):
        """Test find_by_id with different patient IDs."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            for patient_id in [1, 5, 100, 999999]:
                patient = MagicMock()
                mock_session.get.return_value = patient
                
                repo = PatientRepository()
                result = repo.find_by_id(patient_id)
                
                mock_session.get.assert_called_with(Patient, patient_id)
                assert result == patient


# ==========================================================================
# paginate
# ==========================================================================

class TestPaginate:
    def test_paginate_first_page(self):
        """Test paginate with first page."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_query = MagicMock()
            mock_patient.query.order_by.return_value = mock_query
            mock_query.count.return_value = 100
            
            patient1 = MagicMock()
            patient2 = MagicMock()
            mock_query.offset.return_value.limit.return_value.all.return_value = [patient1, patient2]
            
            repo = PatientRepository()
            items, total = repo.paginate(1, 20)
            
            assert len(items) == 2
            assert total == 100
            mock_query.offset.assert_called_once_with(0)
            mock_query.offset.return_value.limit.assert_called_once_with(20)

    def test_paginate_second_page(self):
        """Test paginate with second page (offset calculation)."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_query = MagicMock()
            mock_patient.query.order_by.return_value = mock_query
            mock_query.count.return_value = 100
            mock_query.offset.return_value.limit.return_value.all.return_value = []
            
            repo = PatientRepository()
            items, total = repo.paginate(2, 20)
            
            # Offset should be (2-1) * 20 = 20
            mock_query.offset.assert_called_once_with(20)

    def test_paginate_empty_result(self):
        """Test paginate when no results found."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_query = MagicMock()
            mock_patient.query.order_by.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.offset.return_value.limit.return_value.all.return_value = []
            
            repo = PatientRepository()
            items, total = repo.paginate(1, 20)
            
            assert items == []
            assert total == 0

    def test_paginate_single_item(self):
        """Test paginate with single item."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_query = MagicMock()
            mock_patient.query.order_by.return_value = mock_query
            mock_query.count.return_value = 1
            patient = MagicMock()
            mock_query.offset.return_value.limit.return_value.all.return_value = [patient]
            
            repo = PatientRepository()
            items, total = repo.paginate(1, 20)
            
            assert len(items) == 1
            assert total == 1

    def test_paginate_large_page_size(self):
        """Test paginate with large page size."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_query = MagicMock()
            mock_patient.query.order_by.return_value = mock_query
            mock_query.count.return_value = 50
            mock_query.offset.return_value.limit.return_value.all.return_value = []
            
            repo = PatientRepository()
            items, total = repo.paginate(1, 100)
            
            mock_query.offset.return_value.limit.assert_called_once_with(100)
            assert total == 50


# ==========================================================================
# count
# ==========================================================================

class TestCount:
    def test_count_returns_total(self):
        """Test count returns total number of patients."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_patient.query.count.return_value = 42
            
            repo = PatientRepository()
            result = repo.count()
            
            assert result == 42

    def test_count_zero(self):
        """Test count when no patients exist."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_patient.query.count.return_value = 0
            
            repo = PatientRepository()
            result = repo.count()
            
            assert result == 0

    def test_count_large_number(self):
        """Test count with large number of patients."""
        with patch('app.repositories.patient_repository.Patient') as mock_patient:
            mock_patient.query.count.return_value = 100000
            
            repo = PatientRepository()
            result = repo.count()
            
            assert result == 100000


# ==========================================================================
# add
# ==========================================================================

class TestAdd:
    def test_add_patient(self):
        """Test add method adds patient to session."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            patient = MagicMock()
            
            repo = PatientRepository()
            result = repo.add(patient)
            
            mock_session.add.assert_called_once_with(patient)
            assert result == patient

    def test_add_returns_same_patient(self):
        """Test add returns the same patient object."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            patient = MagicMock()
            patient.id = 123
            
            repo = PatientRepository()
            result = repo.add(patient)
            
            assert result.id == 123

    def test_add_multiple_patients_sequentially(self):
        """Test adding multiple patients sequentially."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            patients = [MagicMock() for _ in range(3)]
            
            repo = PatientRepository()
            results = [repo.add(p) for p in patients]
            
            assert len(results) == 3
            assert mock_session.add.call_count == 3


# ==========================================================================
# commit
# ==========================================================================

class TestCommit:
    def test_commit_calls_session_commit(self):
        """Test commit calls db.session.commit()."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            repo = PatientRepository()
            repo.commit()
            
            mock_session.commit.assert_called_once()

    def test_commit_multiple_times(self):
        """Test commit can be called multiple times."""
        with patch('app.repositories.patient_repository.db.session') as mock_session:
            repo = PatientRepository()
            repo.commit()
            repo.commit()
            repo.commit()
            
            assert mock_session.commit.call_count == 3
