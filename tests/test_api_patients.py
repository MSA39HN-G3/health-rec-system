from unittest.mock import MagicMock
from flask import json
import pytest
from app.api.v1.patients import _patient_service

def test_create_patient_api_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    """Test POST /api/v1/patients successfully creates a patient with all new fields."""
    mock_patient = MagicMock()
    mock_patient.to_dict.return_value = {
        "id": 1,
        "full_name": "Nguyễn Văn A",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "phone": "0987654321",
        "email": "a@example.com",
        "address": "Hà Nội",
        "blood_type": "O+",
        "height": 175.5,
        "weight": 70.0,
        "medical_history": "Không có",
        "allergies": "Không có",
    }

    mock_create = MagicMock(return_value=mock_patient)
    monkeypatch.setattr(_patient_service, "create_patient", mock_create)

    # Create a user with user:manage permission required for creating patients
    role = make_role("manager_role", ["user:manage"])
    manager = make_user(email="manager@test.local", roles=[role])
    headers = auth_header(manager)

    response = client.post(
        "/api/v1/patients",
        data=json.dumps({
            "full_name": "Nguyễn Văn A",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "0987654321",
            "email": "a@example.com",
            "address": "Hà Nội",
            "blood_type": "O+",
            "height": 175.5,
            "weight": 70.0,
            "medical_history": "Không có",
            "allergies": "Không có",
        }),
        headers=headers,
        content_type="application/json"
    )

    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["data"]["id"] == 1
    assert res_data["data"]["blood_type"] == "O+"
    assert res_data["data"]["height"] == 175.5
    assert res_data["data"]["weight"] == 70.0
    assert res_data["data"]["medical_history"] == "Không có"
    assert res_data["data"]["allergies"] == "Không có"

    mock_create.assert_called_once_with(
        full_name="Nguyễn Văn A",
        date_of_birth="1990-01-01",
        gender="male",
        phone="0987654321",
        email="a@example.com",
        address="Hà Nội",
        blood_type="O+",
        height=175.5,
        weight=70.0,
        medical_history="Không có",
        allergies="Không có",
    )


def test_update_patient_api_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    """Test PATCH /api/v1/patients/<id> successfully updates patient with new fields."""
    mock_patient = MagicMock()
    mock_patient.to_dict.return_value = {
        "id": 1,
        "full_name": "Nguyễn Văn A",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "phone": "0987654321",
        "email": "a@example.com",
        "address": "Hà Nội",
        "blood_type": "A-",
        "height": 176.0,
        "weight": 72.5,
        "medical_history": "Tiểu đường",
        "allergies": "Phấn hoa",
    }

    mock_update = MagicMock(return_value=mock_patient)
    monkeypatch.setattr(_patient_service, "update_patient", mock_update)

    # Create a user with user:manage permission required for updating patients
    role = make_role("manager_role", ["user:manage"])
    manager = make_user(email="manager@test.local", roles=[role])
    headers = auth_header(manager)

    response = client.patch(
        "/api/v1/patients/1",
        data=json.dumps({
            "blood_type": "A-",
            "height": 176.0,
            "weight": 72.5,
            "medical_history": "Tiểu đường",
            "allergies": "Phấn hoa",
        }),
        headers=headers,
        content_type="application/json"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data["data"]["blood_type"] == "A-"
    assert res_data["data"]["height"] == 176.0
    assert res_data["data"]["weight"] == 72.5
    assert res_data["data"]["medical_history"] == "Tiểu đường"
    assert res_data["data"]["allergies"] == "Phấn hoa"

    mock_update.assert_called_once_with(
        1,
        full_name=None,
        date_of_birth=None,
        gender=None,
        phone=None,
        email=None,
        address=None,
        blood_type="A-",
        height=176.0,
        weight=72.5,
        medical_history="Tiểu đường",
        allergies="Phấn hoa",
    )


def test_create_health_record_api_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    """Test POST /api/v1/patients/<id>/records successfully creates a health record with symptoms."""
    mock_record = MagicMock()
    mock_record.to_dict.return_value = {
        "id": 5,
        "patient_id": 1,
        "title": "Khám định kỳ",
        "notes": "Bệnh nhân bình thường",
        "symptoms": [{"id": 10, "code": "S1", "name": "Ho"}],
    }

    mock_create = MagicMock(return_value=mock_record)
    monkeypatch.setattr("app.api.v1.patients._record_service", MagicMock(create_record=mock_create))

    # Create a user with record:write permission required for writing records
    role = make_role("doctor_role", ["record:write"])
    doctor = make_user(email="doctor@test.local", roles=[role])
    headers = auth_header(doctor)

    response = client.post(
        "/api/v1/patients/1/records",
        data=json.dumps({
            "title": "Khám định kỳ",
            "notes": "Bệnh nhân bình thường",
            "symptom_ids": ["10"],
        }),
        headers=headers,
        content_type="application/json"
    )

    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["data"]["id"] == 5
    assert len(res_data["data"]["symptoms"]) == 1
    assert res_data["data"]["symptoms"][0]["id"] == 10

    mock_create.assert_called_once_with(
        patient_id=1,
        title="Khám định kỳ",
        visit_date=None,
        doctor_id=None,
        department_id=None,
        notes="Bệnh nhân bình thường",
        diagnosis=None,
        treatment=None,
        symptom_ids=[10],
    )


def test_update_health_record_api_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    """Test PATCH /api/v1/patients/<id>/records/<id> successfully updates a health record symptoms."""
    mock_record = MagicMock()
    mock_record.to_dict.return_value = {
        "id": 5,
        "patient_id": 1,
        "title": "Khám định kỳ cập nhật",
        "symptoms": [{"id": 11, "code": "S2", "name": "Sốt"}],
    }

    mock_update = MagicMock(return_value=mock_record)
    monkeypatch.setattr("app.api.v1.patients._record_service", MagicMock(update_record=mock_update))

    role = make_role("doctor_role", ["record:write"])
    doctor = make_user(email="doctor@test.local", roles=[role])
    headers = auth_header(doctor)

    response = client.patch(
        "/api/v1/patients/1/records/5",
        data=json.dumps({
            "title": "Khám định kỳ cập nhật",
            "symptom_ids": ["11"],
        }),
        headers=headers,
        content_type="application/json"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data["data"]["title"] == "Khám định kỳ cập nhật"
    assert res_data["data"]["symptoms"][0]["id"] == 11

    mock_update.assert_called_once_with(
        1,
        5,
        title="Khám định kỳ cập nhật",
        visit_date=None,
        doctor_id=None,
        department_id=None,
        notes=None,
        diagnosis=None,
        treatment=None,
        symptom_ids=[11],
    )


def test_get_health_records_patient_29_no_auth(client, db_sqlite, monkeypatch):
    """Test that patient 29 records can be accessed without authentication, while patient 1 cannot."""
    mock_list = MagicMock(return_value=([], 0))
    monkeypatch.setattr("app.api.v1.patients._record_service", MagicMock(list_records=mock_list))

    # Without authorization header, patient 29 should succeed (200 OK)
    response = client.get("/api/v1/patients/29/records")
    assert response.status_code == 200
    mock_list.assert_called_once_with(29, 1, 20)

    # Without authorization header, patient 1 should fail (401 Unauthorized)
    response_p1 = client.get("/api/v1/patients/1/records")
    assert response_p1.status_code == 401
