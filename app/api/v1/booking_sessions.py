from flask import Blueprint

from ...common.response import success_response
from ...errors import ValidationException
from ...i18n import translate
from ...middleware import (
    Field,
    current_user,
    validate_body,
    validated,
)
from ...services.booking_session_service import BookingSessionService

bp = Blueprint("booking_sessions", __name__, url_prefix="/api/v1/booking-sessions")
_booking_session_service = BookingSessionService()


@bp.post("")
@validate_body(
    {
        "symptom_ids": Field(list, required=False, default=[]),
        "free_text_symptom": Field(str, required=False, nullable=True),
    }
)
def create_session():
    """Tạo phiên đặt lịch khám mới (Bước 1: Chọn triệu chứng)."""
    data = validated()
    symptom_ids_raw = data.get("symptom_ids") or []
    free_text_symptom = data.get("free_text_symptom")

    # Ép kiểu các phần tử trong danh sách triệu chứng từ string sang int (ID)
    try:
        symptom_ids = [int(sid) for sid in symptom_ids_raw]
    except (ValueError, TypeError):
        raise ValidationException(details={"symptom_ids": "must_be_list_of_integer_strings"})

    user = current_user()
    created_by_user_id = user.id if user else None

    session = _booking_session_service.create_session(
        symptom_ids=symptom_ids,
        free_text_symptom=free_text_symptom,
        created_by_user_id=created_by_user_id,
    )

    return success_response(
        session.to_dict(),
        message=translate("messages.booking_session_created"),
        status_code=201,
    )


@bp.put("/<session_id>/patient")
@validate_body(
    {
        "full_name": Field(str, required=True, min_length=1, max_length=255),
        "date_of_birth": Field(str, required=False, nullable=True),
        "gender": Field(str, required=False, nullable=True),
        "phone": Field(str, required=True, min_length=1, max_length=32),
        "email": Field(str, required=False, nullable=True),
        "address": Field(str, required=False, nullable=True),
    }
)
def update_patient(session_id):
    """Cập nhật thông tin bệnh nhân (Bước 2)."""
    data = validated()
    session = _booking_session_service.update_patient_info(session_id, data)
    return success_response(
        session.to_dict(),
        message=translate("messages.booking_session_patient_updated")
    )


@bp.post("/<session_id>/recommendations")
def get_recommendations(session_id):
    """Sinh gợi ý chuyên khoa AI từ triệu chứng của phiên (Bước 3)."""
    recs = _booking_session_service.get_ai_recommendations(session_id)
    return success_response(
        [r.to_dict() for r in recs],
        message=translate("messages.booking_session_ai_recommended")
    )


@bp.post("/<session_id>/select-department")
@validate_body(
    {
        "department_id": Field(int, required=True, minimum=1),
    }
)
def select_department(session_id):
    """Bệnh nhân chọn khoa (Bước 3)."""
    data = validated()
    session = _booking_session_service.select_department(session_id, data["department_id"])
    return success_response(
        session.to_dict(),
        message=translate("messages.booking_session_department_selected")
    )


@bp.get("/<session_id>/slots")
def get_slots(session_id):
    """Lấy danh sách phòng, bác sĩ và slot trống cho ngày được chọn (Bước 3)."""
    from flask import request
    date_str = request.args.get("date")
    if not date_str:
        raise ValidationException(details={"date": "required"})
    slots = _booking_session_service.get_available_slots(session_id, date_str)
    return success_response(slots)


@bp.post("/<session_id>/confirm")
@validate_body(
    {
        "doctor_id": Field(int, required=True, minimum=1),
        "room_id": Field(int, required=True, minimum=1),
        "schedule_id": Field(int, required=True, minimum=1),
        "appointment_date": Field(str, required=True),
        "start_time": Field(str, required=True),
        "end_time": Field(str, required=True),
    }
)
def confirm_appointment(session_id):
    """Xác nhận đặt lịch và lưu các bản ghi chính thức (Bước 3)."""
    data = validated()
    apt = _booking_session_service.confirm_appointment(session_id, data)
    return success_response(
        apt.to_dict(),
        message=translate("messages.booking_session_booked"),
        status_code=201
    )

