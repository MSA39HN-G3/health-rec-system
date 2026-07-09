from unittest.mock import MagicMock, patch
import datetime
from datetime import date, time
import pytest

from app.errors import BadRequestException, NotFoundException, ConflictException
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

    def test_create_session_only_free_text(self):
        svc, s_repo, sym_repo = _svc()
        session = svc.create_session(
            symptom_ids=[],
            free_text_symptom="Đau đầu âm ỉ",
            created_by_user_id=10
        )
        assert session is not None
        assert session.free_text_symptom == "Đau đầu âm ỉ"
        assert s_repo.add_session_symptom.call_count == 0

    def test_create_session_missing_symptoms_raises_400(self):
        svc, _, _ = _svc()
        with pytest.raises(BadRequestException):
            svc.create_session(symptom_ids=[], free_text_symptom=None)

    def test_create_session_invalid_symptom_id_raises_404(self):
        svc, _, sym_repo = _svc()
        sym_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_session(symptom_ids=[999])

    def test_create_session_db_error_rolls_back(self):
        svc, s_repo, sym_repo = _svc()
        symptom = MagicMock()
        sym_repo.find_by_id.return_value = symptom
        s_repo.commit.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            svc.create_session(symptom_ids=[1])

        s_repo.rollback.assert_called_once()


class TestUpdatePatientInfo:
    def test_update_patient_info_session_not_found(self):
        svc, s_repo, _ = _svc()
        s_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_patient_info("session-invalid", {"phone": "123", "full_name": "Name"})

    def test_update_patient_info_missing_phone_or_name(self):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        s_repo.find_by_id.return_value = session
        with pytest.raises(BadRequestException):
            svc.update_patient_info("session-123", {"phone": "", "full_name": "Name"})
        with pytest.raises(BadRequestException):
            svc.update_patient_info("session-123", {"phone": "123", "full_name": ""})

    def test_update_patient_info_invalid_date_format(self):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        s_repo.find_by_id.return_value = session
        with pytest.raises(BadRequestException):
            svc.update_patient_info("session-123", {"phone": "123", "full_name": "Name", "date_of_birth": "invalid"})

    @patch("app.services.booking_session_service.Patient")
    @patch("app.services.booking_session_service.db.session")
    def test_update_patient_info_existing_patient(self, mock_db_session, mock_patient_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        existing_patient = MagicMock()
        existing_patient.id = 55
        mock_patient_class.query.filter_by.return_value.first.return_value = existing_patient

        patient_data = {
            "phone": "0987654321",
            "full_name": "Nguyen Van Test",
            "date_of_birth": "1995-10-25",
            "gender": "male",
            "email": "test@domain.com",
            "address": "123 Street"
        }

        updated_session = svc.update_patient_info("session-123", patient_data)

        assert updated_session is session
        assert existing_patient.full_name == "Nguyen Van Test"
        assert existing_patient.gender == "male"
        assert existing_patient.email == "test@domain.com"
        assert existing_patient.address == "123 Street"
        assert session.patient_id == 55
        assert session.status == "PATIENT_INFO_COMPLETED"
        assert session.current_step == 2
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.Patient")
    @patch("app.services.booking_session_service.db.session")
    def test_update_patient_info_existing_patient_partial_fields(self, mock_db_session, mock_patient_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        existing_patient = MagicMock()
        existing_patient.id = 55
        existing_patient.full_name = "Original"
        mock_patient_class.query.filter_by.return_value.first.return_value = existing_patient

        patient_data = {
            "phone": "0987654321",
            "full_name": "Nguyen Van Test",
            "date_of_birth": None
        }

        updated_session = svc.update_patient_info("session-123", patient_data)
        assert updated_session is session
        assert existing_patient.full_name == "Nguyen Van Test"
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.Patient")
    @patch("app.services.booking_session_service.db.session")
    def test_update_patient_info_new_patient(self, mock_db_session, mock_patient_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        mock_patient_class.query.filter_by.return_value.first.return_value = None

        patient_data = {
            "phone": "0987654321",
            "full_name": "Nguyen Van Test",
            "date_of_birth": "1995-10-25T00:00:00.000Z",
            "gender": "male",
            "email": "test@domain.com",
            "address": "123 Street"
        }

        updated_session = svc.update_patient_info("session-123", patient_data)

        assert updated_session is session
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestGetAIRecommendations:
    def test_get_ai_recommendations_session_not_found(self):
        svc, s_repo, _ = _svc()
        s_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_ai_recommendations("session-invalid")

    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_existing_recs_not_recommended_status(self, mock_db_session, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        s_repo.find_by_id.return_value = session

        mock_recs = [MagicMock(), MagicMock()]
        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = mock_recs

        res = svc.get_ai_recommendations("session-123")
        assert res == mock_recs
        assert session.status == "AI_RECOMMENDED"
        assert session.current_step == 3
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_existing_recs_already_recommended_status(self, mock_db_session, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "AI_RECOMMENDED"
        s_repo.find_by_id.return_value = session

        mock_recs = [MagicMock(), MagicMock()]
        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = mock_recs

        res = svc.get_ai_recommendations("session-123")
        assert res == mock_recs
        mock_db_session.commit.assert_not_called()

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.Department")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_api_success(self, mock_db_session, mock_ai_rec_class, mock_dept_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        sym1 = MagicMock()
        sym1.name = "Ho"
        session.symptoms = [sym1]
        session.free_text_symptom = "Đau họng"
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = []
        mock_ai_rec_class.query.filter_by.return_value.delete.return_value = 0

        # Use side_effect to dynamically assign arguments to the mocked objects
        def make_rec(**kwargs):
            rec = MagicMock()
            rec.department_id = kwargs.get("department_id")
            rec.confidence_score = kwargs.get("confidence_score")
            rec.model_name = kwargs.get("model_name")
            return rec
        mock_ai_rec_class.side_effect = make_rec

        dept1 = MagicMock()
        dept1.id = 1
        dept1.name = "Khoa Hô hấp"
        mock_dept_class.query.all.return_value = [dept1]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"Chuyen_Khoa": "Khoa Hô hấp", "Do_Chinh_Xac": 0.9, "reasoning": "Ho nhiều"}]
        mock_requests.post.return_value = mock_response

        recs = svc.get_ai_recommendations("session-123")
        assert len(recs) == 1
        assert recs[0].department_id == 1
        assert recs[0].confidence_score == 0.9
        assert session.status == "AI_RECOMMENDED"
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.Department")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_api_success_complex_mapping(self, mock_db_session, mock_ai_rec_class, mock_dept_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        session.symptoms = []
        session.free_text_symptom = "Đau họng"
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = []
        mock_ai_rec_class.query.filter_by.return_value.delete.return_value = 0

        def make_rec(**kwargs):
            rec = MagicMock()
            rec.department_id = kwargs.get("department_id")
            rec.confidence_score = kwargs.get("confidence_score")
            rec.model_name = kwargs.get("model_name")
            return rec
        mock_ai_rec_class.side_effect = make_rec

        dept1 = MagicMock()
        dept1.id = 1
        dept1.name = "Khoa Hô hấp"
        mock_dept_class.query.all.return_value = [dept1]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"Chuyen_Khoa": "Khoa Tim", "Do_Chinh_Xac": 0.8},
            {"Chuyen_Khoa": "Khoa Hô hấp", "Do_Chinh_Xac": 0.9},
            {"Chuyen_Khoa": "Khoa Hô hấp", "Do_Chinh_Xac": 0.95},
            {"Do_Chinh_Xac": 0.5}
        ]
        mock_requests.post.return_value = mock_response

        recs = svc.get_ai_recommendations("session-123")
        assert len(recs) == 1
        assert recs[0].department_id == 1
        assert recs[0].confidence_score == 0.9

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.SymptomService")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_fallback_on_api_error(self, mock_db_session, mock_ai_rec_class, mock_symptom_svc_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        session.symptoms = []
        session.free_text_symptom = None
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = []
        mock_ai_rec_class.query.filter_by.return_value.delete.return_value = 0

        def make_rec(**kwargs):
            rec = MagicMock()
            rec.department_id = kwargs.get("department_id")
            rec.confidence_score = kwargs.get("confidence_score")
            rec.model_name = kwargs.get("model_name")
            return rec
        mock_ai_rec_class.side_effect = make_rec

        # Simulate API Exception
        mock_requests.post.side_effect = Exception("API connection timed out")

        # Mock fallback rule-based recommendations
        mock_symptom_svc = MagicMock()
        mock_symptom_svc_class.return_value = mock_symptom_svc
        mock_symptom_svc.get_recommendations.return_value = [
            {"specialty": {"id": 2, "name": "Khoa Tiêu hóa", "description": "desc"}, "score": 0.8, "explanation": "Rule match"}
        ]

        recs = svc.get_ai_recommendations("session-123")
        assert len(recs) == 1
        assert recs[0].department_id == 2
        assert recs[0].confidence_score == 0.8
        assert recs[0].model_name == "rule-based-fallback"
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.SymptomService")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_api_empty_list_triggers_fallback(self, mock_db_session, mock_ai_rec_class, mock_symptom_svc_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        session.symptoms = []
        session.free_text_symptom = None
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = []
        mock_ai_rec_class.query.filter_by.return_value.delete.return_value = 0

        def make_rec(**kwargs):
            rec = MagicMock()
            rec.department_id = kwargs.get("department_id")
            rec.confidence_score = kwargs.get("confidence_score")
            rec.model_name = kwargs.get("model_name")
            return rec
        mock_ai_rec_class.side_effect = make_rec

        # API returns empty list
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_requests.post.return_value = mock_response

        # Mock fallback rule-based recommendations with duplicates and limits
        mock_symptom_svc = MagicMock()
        mock_symptom_svc_class.return_value = mock_symptom_svc
        mock_symptom_svc.get_recommendations.return_value = [
            {"specialty": {"id": 2, "name": "Khoa Tiêu hóa", "description": "desc"}, "score": 0.8, "explanation": "Rule match"},
            {"specialty": {"id": 2, "name": "Khoa Tiêu hóa", "description": "desc"}, "score": 0.8, "explanation": "Rule match"}, # duplicate
            {"specialty": {"id": 3, "name": "Khoa Nhi", "description": "desc"}, "score": 0.7, "explanation": "Rule match"},
            {"specialty": {"id": 4, "name": "Khoa Ngoại", "description": "desc"}, "score": 0.6, "explanation": "Rule match"},
            {"specialty": {"id": 5, "name": "Khoa Tim", "description": "desc"}, "score": 0.5, "explanation": "Rule match"},
        ]

        recs = svc.get_ai_recommendations("session-123")
        assert len(recs) == 3
        assert recs[0].department_id == 2
        assert recs[1].department_id == 3
        assert recs[2].department_id == 4

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_db_error_resolves_concurrency(self, mock_db_session, mock_ai_rec_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        session.symptoms = []
        session.free_text_symptom = None
        s_repo.find_by_id.return_value = session

        # First query for existing returns empty, second call in except returns mock records
        mock_recs = [MagicMock(), MagicMock()]
        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.side_effect = [
            [], # check at start
            mock_recs # check in exception handler (concurrent request succeeded)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests.post.return_value = mock_response

        # Commit fails (e.g. unique constraint violation because other thread committed)
        mock_db_session.commit.side_effect = Exception("Unique violation")

        res = svc.get_ai_recommendations("session-123")
        assert res == mock_recs
        mock_db_session.rollback.assert_called_once()

    @patch("app.services.booking_session_service.requests")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_ai_recommendations_db_error_raises_exception(self, mock_db_session, mock_ai_rec_class, mock_requests):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.status = "CREATED"
        session.symptoms = []
        session.free_text_symptom = None
        s_repo.find_by_id.return_value = session

        # First query and handler query both return empty
        mock_ai_rec_class.query.filter_by.return_value.order_by.return_value.all.return_value = []
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests.post.return_value = mock_response

        # Commit fails
        mock_db_session.commit.side_effect = Exception("Database disk full")

        with pytest.raises(Exception, match="Database disk full"):
            svc.get_ai_recommendations("session-123")


class TestSelectDepartment:
    def test_select_department_session_not_found(self):
        svc, s_repo, _ = _svc()
        s_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.select_department("session-invalid", 1)

    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_select_department_existing_recommendation(self, mock_db_session, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        rec1 = MagicMock()
        rec1.department_id = 10
        rec2 = MagicMock()
        rec2.department_id = 20
        mock_ai_rec_class.query.filter_by.return_value.all.return_value = [rec1, rec2]

        updated_session = svc.select_department("session-123", 10)
        assert updated_session is session
        assert rec1.is_selected is True
        assert rec2.is_selected is False
        assert session.status == "DEPARTMENT_SELECTED"
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.Department")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_select_department_new_user_selection(self, mock_db_session, mock_ai_rec_class, mock_dept_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.all.return_value = []
        dept = MagicMock()
        dept.id = 30
        mock_dept_class.query.get.return_value = dept

        updated_session = svc.select_department("session-123", 30)
        assert updated_session is session
        mock_db_session.add.assert_called_once()
        assert session.status == "DEPARTMENT_SELECTED"
        mock_db_session.commit.assert_called_once()

    @patch("app.services.booking_session_service.Department")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_select_department_new_user_selection_not_found(self, mock_db_session, mock_ai_rec_class, mock_dept_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.all.return_value = []
        mock_dept_class.query.get.return_value = None

        with pytest.raises(NotFoundException):
            svc.select_department("session-123", 999)


class TestGetAvailableSlots:
    def test_get_available_slots_session_not_found(self):
        svc, s_repo, _ = _svc()
        s_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_available_slots("session-invalid", "2026-07-09")

    def test_get_available_slots_invalid_date_format(self):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        s_repo.find_by_id.return_value = session
        with pytest.raises(BadRequestException):
            svc.get_available_slots("session-123", "invalid-date")

    @patch("app.services.booking_session_service.AIRecommendation")
    def test_get_available_slots_no_department_selected(self, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.first.return_value = None

        with pytest.raises(BadRequestException):
            svc.get_available_slots("session-123", "2026-07-09")

    @patch("app.services.booking_session_service.Room")
    @patch("app.services.booking_session_service.AIRecommendation")
    def test_get_available_slots_no_open_rooms(self, mock_ai_rec_class, mock_room_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        mock_room_class.query.filter_by.return_value.all.return_value = []

        res = svc.get_available_slots("session-123", "2026-07-09")
        assert res == []

    @patch("app.services.booking_session_service.AIRecommendation")
    def test_get_available_slots_fallback_to_rank_1(self, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        s_repo.find_by_id.return_value = session

        # is_selected=True returns None, rank=1 returns rec
        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.side_effect = [None, rec]

        # Room query returns empty to finish early
        with patch("app.services.booking_session_service.Room") as mock_room_class:
            mock_room_class.query.filter_by.return_value.all.return_value = []
            res = svc.get_available_slots("session-123", "2026-07-09")
            assert res == []

    @patch("app.services.booking_session_service.DoctorSchedule")
    @patch("app.services.booking_session_service.Room")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_get_available_slots_success(self, mock_db_session, mock_ai_rec_class, mock_room_class, mock_ds_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        room1 = MagicMock()
        room1.id = 101
        room1.name = "Room A"
        room1.code = "RA"
        mock_room_class.query.filter_by.return_value.all.return_value = [room1]

        # 2026-07-09 is Thursday (weekday() = 3). DOW = (3+1)%7 = 4.
        ds1 = MagicMock()
        ds1.id = 10
        ds1.room = room1
        ds1.doctor = MagicMock()
        # Skipped because effective_from in future
        ds1.effective_from = datetime.date(2026, 8, 1)
        ds1.effective_to = None

        ds2 = MagicMock()
        ds2.id = 11
        ds2.room = room1
        ds2.doctor = MagicMock()
        # Skipped because effective_to in past
        ds2.effective_from = None
        ds2.effective_to = datetime.date(2026, 6, 1)

        ds3 = MagicMock()
        ds3.id = 12
        ds3.room = room1
        ds3.doctor.id = 88
        ds3.doctor.full_name = "Dr. Healthy"
        ds3.doctor.title = "MD"
        ds3.effective_from = None
        ds3.effective_to = None

        mock_ds_class.query.filter.return_value.all.return_value = [ds1, ds2, ds3]

        row = MagicMock()
        row.start_time = datetime.time(9, 0)
        row.end_time = datetime.time(9, 30)
        row.available = True
        mock_db_session.execute.return_value.fetchall.return_value = [row]

        res = svc.get_available_slots("session-123", "2026-07-09")
        assert len(res) == 1
        assert res[0]["schedule_id"] == 12
        assert res[0]["slots"][0]["start_time"] == "09:00"
        assert res[0]["slots"][0]["available"] is True


class TestConfirmAppointment:
    def test_confirm_appointment_session_not_found(self):
        svc, s_repo, _ = _svc()
        s_repo.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.confirm_appointment("session-invalid", {})

    def test_confirm_appointment_patient_info_missing(self):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = None
        s_repo.find_by_id.return_value = session
        with pytest.raises(BadRequestException, match="errors.patient_info_missing"):
            svc.confirm_appointment("session-123", {})

    def test_confirm_appointment_missing_required_fields(self):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session
        with pytest.raises(BadRequestException, match="errors.missing_appointment_required_fields"):
            svc.confirm_appointment("session-123", {"doctor_id": 1})

    @patch("app.services.booking_session_service.AIRecommendation")
    def test_confirm_appointment_no_department_selected(self, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session

        mock_ai_rec_class.query.filter_by.return_value.first.return_value = None

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "2026-07-09", "start_time": "09:00", "end_time": "09:30"
        }
        with pytest.raises(BadRequestException, match="errors.no_department_selected"):
            svc.confirm_appointment("session-123", appt_data)

    @patch("app.services.booking_session_service.AIRecommendation")
    def test_confirm_appointment_fallback_to_rank_1(self, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.side_effect = [None, rec]

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "invalid-date", "start_time": "09:00", "end_time": "09:30"
        }
        with pytest.raises(BadRequestException, match="errors.invalid_date_or_time_format"):
            svc.confirm_appointment("session-123", appt_data)

    @patch("app.services.booking_session_service.AIRecommendation")
    def test_confirm_appointment_invalid_date_or_time_format(self, mock_ai_rec_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "invalid", "start_time": "09:00", "end_time": "09:30"
        }
        with pytest.raises(BadRequestException, match="errors.invalid_date_or_time_format"):
            svc.confirm_appointment("session-123", appt_data)

    @patch("app.services.booking_session_service.DoctorSchedule")
    @patch("app.services.booking_session_service.AIRecommendation")
    def test_confirm_appointment_schedule_not_found(self, mock_ai_rec_class, mock_ds_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        mock_ds_class.query.get.return_value = None

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "2026-07-09", "start_time": "09:00", "end_time": "09:30"
        }
        with pytest.raises(NotFoundException):
            svc.confirm_appointment("session-123", appt_data)

    @patch("app.services.booking_session_service.Appointment")
    @patch("app.services.booking_session_service.DoctorSchedule")
    @patch("app.services.booking_session_service.AIRecommendation")
    def test_confirm_appointment_slot_already_booked(self, mock_ai_rec_class, mock_ds_class, mock_appt_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.patient_id = 99
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        ds = MagicMock()
        ds.max_patients_per_slot = 2
        mock_ds_class.query.get.return_value = ds

        # Simulate slot already booked up to capacity
        mock_appt_class.query.filter_by.return_value.filter.return_value.count.return_value = 2

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "2026-07-09", "start_time": "09:00", "end_time": "09:30"
        }
        with pytest.raises(ConflictException):
            svc.confirm_appointment("session-123", appt_data)

    @patch("app.services.booking_session_service.Appointment")
    @patch("app.services.booking_session_service.AppointmentStatusHistory")
    @patch("app.services.booking_session_service.DoctorSchedule")
    @patch("app.services.booking_session_service.AIRecommendation")
    @patch("app.services.booking_session_service.db.session")
    def test_confirm_appointment_success(self, mock_db_session, mock_ai_rec_class, mock_ds_class, mock_history_class, mock_appt_class):
        svc, s_repo, _ = _svc()
        session = MagicMock()
        session.id = "session-123"
        session.patient_id = 99
        session.free_text_symptom = "ho"
        s_repo.find_by_id.return_value = session

        rec = MagicMock()
        rec.department_id = 5
        mock_ai_rec_class.query.filter_by.return_value.first.return_value = rec

        ds = MagicMock()
        ds.max_patients_per_slot = 3
        mock_ds_class.query.get.return_value = ds

        mock_appt_class.query.filter_by.return_value.filter.return_value.count.return_value = 1

        appt_data = {
            "doctor_id": 1, "room_id": 2, "schedule_id": 3,
            "appointment_date": "2026-07-09", "start_time": "09:00:00", "end_time": "09:30:00"
        }

        # Setup constructor for mock Appointment
        mock_appt_instance = MagicMock()
        mock_appt_instance.status = "pending"
        mock_appt_class.return_value = mock_appt_instance

        appt = svc.confirm_appointment("session-123", appt_data)
        assert appt is not None
        assert appt.status == "pending"
        assert session.status == "BOOKED"
        assert session.current_step == 3
        assert mock_db_session.add.call_count == 2
        mock_db_session.commit.assert_called_once()
