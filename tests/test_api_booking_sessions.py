from unittest.mock import MagicMock

from flask import json

from app.api.v1.booking_sessions import _booking_session_service


def test_create_booking_session_api_success(client, monkeypatch):
    """Test POST /api/v1/booking-sessions successfully creates a session."""
    mock_session = MagicMock()
    mock_session.to_dict.return_value = {
        "id": "test-uuid-123",
        "status": "CREATED",
        "current_step": 1,
        "free_text_symptom": "Đau mỏi vai gáy",
        "symptoms": []
    }

    mock_create = MagicMock(return_value=mock_session)
    monkeypatch.setattr(_booking_session_service, "create_session", mock_create)

    response = client.post(
        "/api/v1/booking-sessions",
        data=json.dumps({
            "symptom_ids": ["1", "2"],
            "free_text_symptom": "Đau mỏi vai gáy"
        }),
        content_type="application/json"
    )

    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["data"]["id"] == "test-uuid-123"
    assert res_data["data"]["status"] == "CREATED"
    mock_create.assert_called_once_with(
        symptom_ids=[1, 2],
        free_text_symptom="Đau mỏi vai gáy",
        created_by_user_id=None
    )
def test_create_booking_session_api_invalid_symptoms(client):
    """Test POST /api/v1/booking-sessions raises 422 on invalid input types."""
    response = client.post(
        "/api/v1/booking-sessions",
        data=json.dumps({
            "symptom_ids": ["not-an-int"]
        }),
        content_type="application/json"
    )
    assert response.status_code == 422


def test_update_patient_info_api_success(client, monkeypatch):
    """Test PUT /api/v1/booking-sessions/<id>/patient successfully updates patient."""
    mock_session = MagicMock()
    mock_session.to_dict.return_value = {
        "id": "test-uuid-123",
        "status": "PATIENT_INFO_COMPLETED",
        "current_step": 2,
        "patient_id": 42
    }

    mock_update = MagicMock(return_value=mock_session)
    monkeypatch.setattr(_booking_session_service, "update_patient_info", mock_update)

    response = client.put(
        "/api/v1/booking-sessions/test-uuid-123/patient",
        data=json.dumps({
            "full_name": "Nguyen Van Patient",
            "phone": "0987654321",
            "gender": "male",
            "date_of_birth": "1995-05-15"
        }),
        content_type="application/json"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data["data"]["status"] == "PATIENT_INFO_COMPLETED"
    mock_update.assert_called_once()


def test_get_recommendations_api_success(client, monkeypatch):
    """Test POST /api/v1/booking-sessions/<id>/recommendations successfully gets AI recommendations."""
    mock_rec = MagicMock()
    mock_rec.to_dict.return_value = {
        "department_id": 1,
        "rank": 1,
        "confidence_score": 0.95,
        "reasoning": "Symptoms match specialty perfectly"
    }

    mock_get_recs = MagicMock(return_value=[mock_rec])
    monkeypatch.setattr(_booking_session_service, "get_ai_recommendations", mock_get_recs)

    response = client.post(
        "/api/v1/booking-sessions/test-uuid-123/recommendations"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert len(res_data["data"]) == 1
    assert res_data["data"][0]["department_id"] == 1
    mock_get_recs.assert_called_once_with("test-uuid-123")


def test_select_department_api_success(client, monkeypatch):
    """Test POST /api/v1/booking-sessions/<id>/select-department successfully selects department."""
    mock_session = MagicMock()
    mock_session.to_dict.return_value = {
        "id": "test-uuid-123",
        "status": "DEPARTMENT_SELECTED",
        "current_step": 3
    }

    mock_select = MagicMock(return_value=mock_session)
    monkeypatch.setattr(_booking_session_service, "select_department", mock_select)

    response = client.post(
        "/api/v1/booking-sessions/test-uuid-123/select-department",
        data=json.dumps({
            "department_id": 1
        }),
        content_type="application/json"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data["data"]["status"] == "DEPARTMENT_SELECTED"
    mock_select.assert_called_once_with("test-uuid-123", 1)


def test_get_slots_api_success(client, monkeypatch):
    """Test GET /api/v1/booking-sessions/<id>/slots successfully gets available slots."""
    mock_slots = [
        {
            "room": {"id": 1, "name": "Room A"},
            "doctor": {"id": 2, "full_name": "Doctor B"},
            "slots": [{"start_time": "08:00", "end_time": "08:30", "available": True}]
        }
    ]

    mock_get_slots = MagicMock(return_value=mock_slots)
    monkeypatch.setattr(_booking_session_service, "get_available_slots", mock_get_slots)

    response = client.get(
        "/api/v1/booking-sessions/test-uuid-123/slots?date=2026-07-15"
    )

    assert response.status_code == 200
    res_data = response.get_json()
    assert len(res_data["data"]) == 1
    assert res_data["data"][0]["doctor"]["full_name"] == "Doctor B"
    mock_get_slots.assert_called_once_with("test-uuid-123", "2026-07-15")


def test_confirm_appointment_api_success(client, monkeypatch):
    """Test POST /api/v1/booking-sessions/<id>/confirm successfully confirms booking."""
    mock_apt = MagicMock()
    mock_apt.to_dict.return_value = {
        "code": "APT-20260715-1234",
        "status": "pending",
        "doctor_id": 2,
        "room_id": 1,
        "appointment_date": "2026-07-15"
    }

    mock_confirm = MagicMock(return_value=mock_apt)
    monkeypatch.setattr(_booking_session_service, "confirm_appointment", mock_confirm)

    response = client.post(
        "/api/v1/booking-sessions/test-uuid-123/confirm",
        data=json.dumps({
            "doctor_id": 2,
            "room_id": 1,
            "schedule_id": 3,
            "appointment_date": "2026-07-15",
            "start_time": "08:00",
            "end_time": "08:30"
        }),
        content_type="application/json"
    )

    assert response.status_code == 201
    res_data = response.get_json()
    assert res_data["data"]["code"] == "APT-20260715-1234"
    mock_confirm.assert_called_once()

