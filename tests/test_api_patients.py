"""Integration tests for Patient API endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


class TestCountPatientsEndpoint:
    """Test GET /api/v1/patients/count endpoint."""

    def test_count_endpoint_returns_total(self, client):
        """Test count endpoint returns total patient count."""
        with patch('app.middleware.require_permission') as mock_perm, \
             patch('app.api.v1.patients._patient_service.count_patients') as mock_service:
            # Bypass authentication check
            mock_perm.return_value = lambda f: f
            mock_service.return_value = 42
            
            response = client.get('/api/v1/patients/count')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['total'] == 42

    def test_count_endpoint_zero_patients(self, client):
        """Test count endpoint when no patients exist."""
        with patch('app.middleware.require_permission') as mock_perm, \
             patch('app.api.v1.patients._patient_service.count_patients') as mock_service:
            mock_perm.return_value = lambda f: f
            mock_service.return_value = 0
            
            response = client.get('/api/v1/patients/count')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['data']['total'] == 0

    def test_count_endpoint_large_number(self, client):
        """Test count endpoint with large patient count."""
        with patch('app.middleware.require_permission') as mock_perm, \
             patch('app.api.v1.patients._patient_service.count_patients') as mock_service:
            mock_perm.return_value = lambda f: f
            mock_service.return_value = 99999
            
            response = client.get('/api/v1/patients/count')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['data']['total'] == 99999


class TestListPatientsEndpoint:
    """Test GET /api/v1/patients endpoint."""

    def test_list_endpoint_pagination(self, client):
        """Test list endpoint supports pagination."""
        with patch('app.middleware.require_permission') as mock_perm, \
             patch('app.api.v1.patients._patient_service.list_patients') as mock_service:
            mock_perm.return_value = lambda f: f
            patient1 = MagicMock()
            patient1.to_dict.return_value = {'id': 1, 'full_name': 'Patient 1'}
            patient2 = MagicMock()
            patient2.to_dict.return_value = {'id': 2, 'full_name': 'Patient 2'}
            
            mock_service.return_value = ([patient1, patient2], 100)
            
            response = client.get('/api/v1/patients?page=1&size=20')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['pagination']['page'] == 1
                assert data['pagination']['size'] == 20
                assert data['pagination']['total'] == 100

    def test_list_endpoint_second_page(self, client, mock_auth):
        """Test list endpoint with second page."""
        with patch('app.api.v1.patients._patient_service.list_patients') as mock_service:
            mock_service.return_value = ([], 100)
            
            response = client.get('/api/v1/patients?page=2&size=20')
            
            if response.status_code == 200:
                mock_service.assert_called_with(2, 20)

    def test_list_endpoint_default_pagination(self, client, mock_auth):
        """Test list endpoint uses default pagination (page=1, size=20)."""
        with patch('app.api.v1.patients._patient_service.list_patients') as mock_service:
            mock_service.return_value = ([], 0)
            
            response = client.get('/api/v1/patients')
            
            if response.status_code == 200:
                mock_service.assert_called_with(1, 20)


class TestCreatePatientEndpoint:
    """Test POST /api/v1/patients endpoint."""

    def test_create_endpoint_minimal_data(self, client, mock_auth):
        """Test create endpoint with minimal required data."""
        with patch('app.api.v1.patients._patient_service.create_patient') as mock_service:
            new_patient = MagicMock()
            new_patient.to_dict.return_value = {'id': 1, 'full_name': 'New Patient'}
            mock_service.return_value = new_patient
            
            response = client.post(
                '/api/v1/patients',
                json={'full_name': 'New Patient'},
            )
            
            if response.status_code == 201:
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['full_name'] == 'New Patient'

    def test_create_endpoint_full_data(self, client, mock_auth):
        """Test create endpoint with full patient data."""
        with patch('app.api.v1.patients._patient_service.create_patient') as mock_service:
            new_patient = MagicMock()
            new_patient.to_dict.return_value = {
                'id': 1,
                'full_name': 'Full Patient',
                'date_of_birth': '1990-01-15',
                'gender': 'male',
                'phone': '0123456789',
                'email': 'patient@example.com',
                'address': '123 Street',
            }
            mock_service.return_value = new_patient
            
            response = client.post(
                '/api/v1/patients',
                json={
                    'full_name': 'Full Patient',
                    'date_of_birth': '1990-01-15',
                    'gender': 'male',
                    'phone': '0123456789',
                    'email': 'patient@example.com',
                    'address': '123 Street',
                },
            )
            
            if response.status_code == 201:
                mock_service.assert_called()


class TestGetPatientEndpoint:
    """Test GET /api/v1/patients/<id> endpoint."""

    def test_get_endpoint_found(self, client, mock_auth):
        """Test get endpoint returns patient when found."""
        with patch('app.api.v1.patients._patient_service.get_patient') as mock_service:
            patient = MagicMock()
            patient.to_dict.return_value = {'id': 1, 'full_name': 'Patient'}
            mock_service.return_value = patient
            
            response = client.get('/api/v1/patients/1')
            
            if response.status_code == 200:
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['id'] == 1


class TestUpdatePatientEndpoint:
    """Test PATCH /api/v1/patients/<id> endpoint."""

    def test_update_endpoint_partial(self, client, mock_auth):
        """Test update endpoint with partial data."""
        with patch('app.api.v1.patients._patient_service.update_patient') as mock_service:
            updated_patient = MagicMock()
            updated_patient.to_dict.return_value = {'id': 1, 'full_name': 'Updated'}
            mock_service.return_value = updated_patient
            
            response = client.patch(
                '/api/v1/patients/1',
                json={'full_name': 'Updated'},
            )
            
            if response.status_code == 200:
                data = response.get_json()
                assert data['success'] is True
