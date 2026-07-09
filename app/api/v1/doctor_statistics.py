"""Controller quản lý thống kê bác sĩ.

Cung cấp:
  - GET /api/v1/doctors/<doctor_id>/statistics       -> thống kê của bác sĩ
  - POST /api/v1/doctors/<doctor_id>/statistics/recalculate -> tính lại thống kê
  - GET /api/v1/doctors/statistics/top-rated          -> bác sĩ được đánh giá cao
  - GET /api/v1/doctors/statistics/most-active         -> bác sĩ có nhiều lịch hẹn nhất
"""
from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...middleware import (
    Field,
    current_user,
    require_permission,
    validate_query,
    validated_query,
)
from ...services.doctor_statistics_service import DoctorStatisticsService

bp = Blueprint("doctor_statistics", __name__, url_prefix="/api/v1/doctors")

_service = DoctorStatisticsService()


# === GET Statistics ===
@bp.get("/<int:doctor_id>/statistics")
@require_permission(Permission.DEPARTMENT_MANAGE)
def get_doctor_statistics(doctor_id):
    stats = _service.get_doctor_statistics(
        actor=current_user(),
        doctor_id=doctor_id,
    )
    return success_response(stats.to_dict())


# === Recalculate Statistics (Admin only) ===
@bp.post("/<int:doctor_id>/statistics/recalculate")
@require_permission(Permission.DEPARTMENT_MANAGE)
def recalculate_statistics(doctor_id):
    stats = _service.recalculate_statistics(
        actor=current_user(),
        doctor_id=doctor_id,
    )
    return success_response(stats.to_dict(), message="Đã tính lại thống kê")


# === Top Rated Doctors ===
@bp.get("/statistics/top-rated")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "limit": Field(int, required=False, default=10, minimum=1, maximum=50),
    }
)
def get_top_rated_doctors():
    q = validated_query()
    stats = _service.get_top_rated_doctors(
        actor=current_user(),
        limit=q["limit"],
    )
    return success_response([s.to_dict() for s in stats])


# === Most Active Doctors ===
@bp.get("/statistics/most-active")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "limit": Field(int, required=False, default=10, minimum=1, maximum=50),
    }
)
def get_most_active_doctors():
    q = validated_query()
    stats = _service.get_most_active_doctors(
        actor=current_user(),
        limit=q["limit"],
    )
    return success_response([s.to_dict() for s in stats])


# === All Statistics (Admin only) ===
@bp.get("/statistics/all")
@require_permission(Permission.DEPARTMENT_MANAGE)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def get_all_statistics():
    q = validated_query()
    items, total = _service.get_all_statistics(
        actor=current_user(),
        page=q["page"],
        size=q["size"],
    )
    return paginated_response(
        [s.to_dict() for s in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )
