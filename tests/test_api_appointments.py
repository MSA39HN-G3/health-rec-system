"""Test API cho /api/v1/appointments — kiểm tra permission + wiring endpoint."""
from unittest.mock import MagicMock

from flask import json

from app.api.v1.appointments import _service


def _mock_appointment(**overrides):
    apt = MagicMock()
    apt.to_dict.return_value = {
        "id": 1,
        "code": "APT-20260715-0042",
        "patient_id": 1,
        "department_id": 1,
        "doctor_id": 1,
        "status": "pending",
        **overrides,
    }
    return apt


def test_list_appointments_requires_permission(client, db_sqlite, make_role, make_user, auth_header):
    role = make_role("no_perm_role", [])
    user = make_user(email="noperm@test.local", roles=[role])
    headers = auth_header(user)

    response = client.get("/api/v1/appointments", headers=headers)
    assert response.status_code == 403


def test_list_appointments_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    apt = _mock_appointment()
    monkeypatch.setattr(_service, "list_appointments", MagicMock(return_value=([apt], 1)))

    role = make_role("appointment_viewer", ["appointment:read"])
    user = make_user(email="viewer@test.local", roles=[role])
    headers = auth_header(user)

    response = client.get("/api/v1/appointments?page=1&size=20", headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"][0]["code"] == "APT-20260715-0042"
    assert body["meta"]["totalPage"] == 1


def test_get_appointment_not_found(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    from app.errors import NotFoundException

    monkeypatch.setattr(
        _service, "get_appointment", MagicMock(side_effect=NotFoundException("errors.appointment_not_found"))
    )

    role = make_role("appointment_viewer2", ["appointment:read"])
    user = make_user(email="viewer2@test.local", roles=[role])
    headers = auth_header(user)

    response = client.get("/api/v1/appointments/999", headers=headers)
    assert response.status_code == 404


def test_update_status_requires_manage_permission(client, db_sqlite, make_role, make_user, auth_header):
    # Chỉ có quyền read, không có manage -> 403 khi đổi trạng thái.
    role = make_role("appointment_read_only", ["appointment:read"])
    user = make_user(email="readonly@test.local", roles=[role])
    headers = auth_header(user)

    response = client.patch(
        "/api/v1/appointments/1/status",
        data=json.dumps({"status": "confirmed"}),
        headers=headers,
        content_type="application/json",
    )
    assert response.status_code == 403


def test_update_status_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    apt = _mock_appointment(status="confirmed")
    mock_update = MagicMock(return_value=apt)
    monkeypatch.setattr(_service, "update_status", mock_update)

    role = make_role("appointment_manager", ["appointment:manage"])
    user = make_user(email="manager2@test.local", roles=[role])
    headers = auth_header(user)

    response = client.patch(
        "/api/v1/appointments/1/status",
        data=json.dumps({"status": "confirmed", "note": "Đã xác nhận qua điện thoại"}),
        headers=headers,
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "confirmed"
    _, kwargs = mock_update.call_args
    assert kwargs["note"] == "Đã xác nhận qua điện thoại"
    assert mock_update.call_args[0][0] == 1
    assert mock_update.call_args[0][1] == "confirmed"


def test_update_status_invalid_value_rejected(client, db_sqlite, make_role, make_user, auth_header):
    role = make_role("appointment_manager2", ["appointment:manage"])
    user = make_user(email="manager3@test.local", roles=[role])
    headers = auth_header(user)

    response = client.patch(
        "/api/v1/appointments/1/status",
        data=json.dumps({"status": "bogus"}),
        headers=headers,
        content_type="application/json",
    )
    assert response.status_code == 422


def test_cancel_appointment_success(client, db_sqlite, monkeypatch, make_role, make_user, auth_header):
    apt = _mock_appointment(status="cancelled", cancel_reason="Bệnh nhân bận")
    mock_cancel = MagicMock(return_value=apt)
    monkeypatch.setattr(_service, "cancel_appointment", mock_cancel)

    role = make_role("appointment_manager3", ["appointment:manage"])
    user = make_user(email="manager4@test.local", roles=[role])
    headers = auth_header(user)

    response = client.post(
        "/api/v1/appointments/1/cancel",
        data=json.dumps({"reason": "Bệnh nhân bận"}),
        headers=headers,
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "cancelled"
    mock_cancel.assert_called_once()
