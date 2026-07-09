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
