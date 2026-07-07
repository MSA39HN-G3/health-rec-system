from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...i18n import translate
from ...middleware import (
    Field,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.health_record_service import HealthRecordService
from ...services.patient_service import PatientService

bp = Blueprint("patients", __name__, url_prefix="/api/v1/patients")

_patient_service = PatientService()
_record_service = HealthRecordService()


@bp.get("/count")
@require_permission(Permission.USER_READ)
def count_patients():
    """Lấy số lượng bệnh nhân tổng cộng."""
    total = _patient_service.count_patients()
    return success_response({"total": total})


@bp.get("")
@require_permission(Permission.USER_READ)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def list_patients():
    q = validated_query()
    items, total = _patient_service.list_patients(q["page"], q["size"])
    return paginated_response(
        [p.to_dict() for p in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.post("")
@require_permission(Permission.USER_MANAGE)
@validate_body(
    {
        "full_name": Field(str, required=True, min_length=1, max_length=255),
        "date_of_birth": Field(str, required=False),
        "gender": Field(str, required=False, min_length=1, max_length=32),
        "phone": Field(str, required=False, max_length=32),
        "email": Field(str, required=False, max_length=255),
        "address": Field(str, required=False, max_length=2000),
    }
)
def create_patient():
    data = validated()
    patient = _patient_service.create_patient(
        full_name=data["full_name"],
        date_of_birth=data.get("date_of_birth"),
        gender=data.get("gender"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
    )
    return success_response(
        patient.to_dict(),
        message=translate("messages.patient_created"),
        status_code=201,
    )


@bp.get("/<int:patient_id>")
@require_permission(Permission.USER_READ)
def get_patient(patient_id):
    patient = _patient_service.get_patient(patient_id)
    return success_response(patient.to_dict())


@bp.patch("/<int:patient_id>")
@require_permission(Permission.USER_MANAGE)
@validate_body(
    {
        "full_name": Field(str, required=False, min_length=1, max_length=255),
        "date_of_birth": Field(str, required=False),
        "gender": Field(str, required=False, min_length=1, max_length=32),
        "phone": Field(str, required=False, max_length=32),
        "email": Field(str, required=False, max_length=255),
        "address": Field(str, required=False, max_length=2000),
    }
)
def update_patient(patient_id):
    data = validated()
    patient = _patient_service.update_patient(
        patient_id,
        full_name=data.get("full_name"),
        date_of_birth=data.get("date_of_birth"),
        gender=data.get("gender"),
        phone=data.get("phone"),
        email=data.get("email"),
        address=data.get("address"),
    )
    return success_response(
        patient.to_dict(),
        message=translate("messages.patient_updated"),
    )


@bp.get("/<int:patient_id>/records")
@require_permission(Permission.RECORD_READ)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def list_patient_records(patient_id):
    q = validated_query()
    items, total = _record_service.list_records(
        patient_id, q["page"], q["size"]
    )
    return paginated_response(
        [r.to_dict() for r in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.post("/<int:patient_id>/records")
@require_permission(Permission.RECORD_WRITE)
@validate_body(
    {
        "title": Field(str, required=True, min_length=1, max_length=255),
        "visit_date": Field(str, required=False),
        "doctor_id": Field(int, required=False, minimum=1),
        "department_id": Field(int, required=False, minimum=1),
        "notes": Field(str, required=False, max_length=5000),
        "diagnosis": Field(str, required=False, max_length=5000),
        "treatment": Field(str, required=False, max_length=5000),
    }
)
def create_health_record(patient_id):
    data = validated()
    record = _record_service.create_record(
        patient_id=patient_id,
        title=data["title"],
        visit_date=data.get("visit_date"),
        doctor_id=data.get("doctor_id"),
        department_id=data.get("department_id"),
        notes=data.get("notes"),
        diagnosis=data.get("diagnosis"),
        treatment=data.get("treatment"),
    )
    return success_response(
        record.to_dict(),
        message=translate("messages.health_record_created"),
        status_code=201,
    )


@bp.get("/<int:patient_id>/records/<int:record_id>")
@require_permission(Permission.RECORD_READ)
def get_health_record(patient_id, record_id):
    record = _record_service.get_record(patient_id, record_id)
    return success_response(record.to_dict())


@bp.patch("/<int:patient_id>/records/<int:record_id>")
@require_permission(Permission.RECORD_WRITE)
@validate_body(
    {
        "title": Field(str, required=False, min_length=1, max_length=255),
        "visit_date": Field(str, required=False),
        "doctor_id": Field(int, required=False, minimum=1, nullable=True),
        "department_id": Field(int, required=False, minimum=1, nullable=True),
        "notes": Field(str, required=False, max_length=5000, nullable=True),
        "diagnosis": Field(str, required=False, max_length=5000, nullable=True),
        "treatment": Field(str, required=False, max_length=5000, nullable=True),
    }
)
def update_health_record(patient_id, record_id):
    data = validated()
    record = _record_service.update_record(
        patient_id,
        record_id,
        title=data.get("title"),
        visit_date=data.get("visit_date"),
        doctor_id=data.get("doctor_id"),
        department_id=data.get("department_id"),
        notes=data.get("notes"),
        diagnosis=data.get("diagnosis"),
        treatment=data.get("treatment"),
    )
    return success_response(
        record.to_dict(),
        message=translate("messages.health_record_updated"),
    )
