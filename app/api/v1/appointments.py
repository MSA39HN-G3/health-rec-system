"""Controller quản lý lịch hẹn (đã đặt qua kiosk) — dành cho staff/admin.

Cung cấp:
  - GET   /api/v1/appointments               -> danh sách (phân trang + lọc)
  - GET   /api/v1/appointments/<id>          -> chi tiết
  - GET   /api/v1/appointments/<id>/history  -> lịch sử đổi trạng thái
  - PATCH /api/v1/appointments/<id>/status   -> đổi trạng thái
  - POST  /api/v1/appointments/<id>/cancel   -> hủy lịch hẹn

Phân quyền: appointment:read (xem), appointment:manage (đổi trạng thái/hủy).
"""
from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...i18n import translate
from ...middleware import (
    Field,
    current_user,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.appointment_service import VALID_STATUSES, AppointmentService

bp = Blueprint("appointments", __name__, url_prefix="/api/v1/appointments")

_service = AppointmentService()


@bp.get("")
@require_permission(Permission.APPOINTMENT_READ)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
        "date_from": Field(str, required=False),
        "date_to": Field(str, required=False),
        "status": Field(str, required=False, choices=VALID_STATUSES),
        "doctor_id": Field(int, required=False, minimum=1),
        "department_id": Field(int, required=False, minimum=1),
        "patient_id": Field(int, required=False, minimum=1),
    }
)
def list_appointments():
    q = validated_query()
    items, total = _service.list_appointments(
        q["page"],
        q["size"],
        date_from=q.get("date_from"),
        date_to=q.get("date_to"),
        status=q.get("status"),
        doctor_id=q.get("doctor_id"),
        department_id=q.get("department_id"),
        patient_id=q.get("patient_id"),
    )
    return paginated_response(
        [a.to_dict() for a in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.get("/<int:appointment_id>")
@require_permission(Permission.APPOINTMENT_READ)
def get_appointment(appointment_id):
    appointment = _service.get_appointment(appointment_id)
    return success_response(appointment.to_dict())


@bp.get("/<int:appointment_id>/history")
@require_permission(Permission.APPOINTMENT_READ)
def get_appointment_history(appointment_id):
    history = _service.get_status_history(appointment_id)
    return success_response([h.to_dict() for h in history])


@bp.patch("/<int:appointment_id>/status")
@require_permission(Permission.APPOINTMENT_MANAGE)
@validate_body(
    {
        "status": Field(str, required=True, choices=VALID_STATUSES),
        "note": Field(str, required=False, max_length=1000),
    }
)
def update_appointment_status(appointment_id):
    data = validated()
    appointment = _service.update_status(
        appointment_id,
        data["status"],
        changed_by=current_user().id,
        note=data.get("note"),
    )
    return success_response(
        appointment.to_dict(),
        message=translate("messages.appointment_status_updated"),
    )


@bp.post("/<int:appointment_id>/cancel")
@require_permission(Permission.APPOINTMENT_MANAGE)
@validate_body(
    {
        "reason": Field(str, required=False, max_length=1000),
    }
)
def cancel_appointment(appointment_id):
    data = validated()
    appointment = _service.cancel_appointment(
        appointment_id,
        reason=data.get("reason"),
        changed_by=current_user().id,
    )
    return success_response(
        appointment.to_dict(),
        message=translate("messages.appointment_cancelled"),
    )
