from unittest.mock import MagicMock

import pytest

from app.errors import BadRequestException, NotFoundException
from app.services.booking_session_service import BookingSessionService


def _svc(**kwargs):
    booking_session_repo = kwargs.get("booking_session_repo", MagicMock())
    symptom_repo = kwargs.get("symptom_repo", MagicMock())
    return BookingSessionService(
        booking_session_repository=booking_session_repo,
        symptom_repository=symptom_repo
    ), booking_session_repo, symptom_repo


class TestCreateBookingSession:
    def test_create_session_success(self):
        svc, s_repo, sym_repo = _svc()
        symptom = MagicMock()
        sym_repo.find_by_id.return_value = symptom

        session = svc.create_session(
            symptom_ids=[1, 2],
            free_text_symptom="Đau đầu âm ỉ",
            created_by_user_id=10
        )

        assert session is not None
        assert session.id is not None
        assert session.status == "CREATED"
        assert session.current_step == 1
        assert session.free_text_symptom == "Đau đầu âm ỉ"
        assert session.created_by_user_id == 10

        assert s_repo.add.call_count == 1
        assert s_repo.add_session_symptom.call_count == 2
        s_repo.commit.assert_called_once()

    def test_create_session_missing_symptoms_raises_400(self):
        svc, _, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.create_session(symptom_ids=[], free_text_symptom=None)

    def test_create_session_invalid_symptom_id_raises_404(self):
        svc, _, sym_repo = _svc()
        sym_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_session(symptom_ids=[999])
