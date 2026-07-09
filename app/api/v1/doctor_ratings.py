"""Controller quản lý đánh giá bác sĩ từ bệnh nhân.

Cung cấp:
  - POST   /api/v1/ratings                      -> tạo đánh giá mới
  - GET    /api/v1/doctors/<doctor_id>/ratings  -> xem đánh giá của bác sĩ
  - GET    /api/v1/ratings/<id>                -> xem chi tiết đánh giá
  - PATCH  /api/v1/ratings/<id>                -> cập nhật đánh giá
  - DELETE /api/v1/ratings/<id>                -> xóa đánh giá
  - GET    /api/v1/doctors/<doctor_id>/ratings/distribution -> phân bố đánh giá
"""
from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission, Role
from ...errors import ValidationException
from ...middleware import (
    Field,
    current_user,
    require_permission,
    require_role,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.doctor_rating_service import DoctorRatingService

bp = Blueprint("doctor_ratings", __name__, url_prefix="/api/v1")

_service = DoctorRatingService()


# === CREATE Rating ===
@bp.post("/ratings")
@require_permission(Permission.RATING_WRITE)
@validate_body(
    {
        "doctor_id": Field(int, required=True, minimum=1),
        "patient_id": Field(int, required=True, minimum=1),
        "appointment_id": Field(int, required=False, minimum=1),
        "rating": Field(int, required=True, minimum=1, maximum=5),
        "comment": Field(str, required=False, max_length=2000),
    }
)
def create_rating():
    data = validated()
    rating = _service.create_rating(
        actor=current_user(),
        data=data,
    )
    return success_response(
        rating.to_dict(),
        status_code=201,
    )


# === GET Doctor Ratings ===
@bp.get("/doctors/<int:doctor_id>/ratings")
@require_permission(Permission.RATING_READ)
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
    }
)
def get_doctor_ratings(doctor_id):
    q = validated_query()
    items, total = _service.get_doctor_ratings(
        actor=current_user(),
        doctor_id=doctor_id,
        page=q["page"],
        size=q["size"],
    )
    return paginated_response(
        [r.to_dict() for r in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


# === GET Rating Distribution ===
@bp.get("/doctors/<int:doctor_id>/ratings/distribution")
def get_rating_distribution(doctor_id):
    """Public endpoint - ai cũng xem được phân bố đánh giá."""
    distribution = _service.get_rating_distribution(
        actor=current_user(),
        doctor_id=doctor_id,
    )
    return success_response(distribution)


# === GET One Rating ===
@bp.get("/ratings/<int:rating_id>")
@require_permission(Permission.RATING_READ)
def get_rating(rating_id):
    rating = _service.get_rating(
        actor=current_user(),
        rating_id=rating_id,
    )
    return success_response(rating.to_dict())


# === UPDATE Rating ===
@bp.patch("/ratings/<int:rating_id>")
@require_permission(Permission.RATING_WRITE)
@validate_body(
    {
        "rating": Field(int, required=False, minimum=1, maximum=5),
        "comment": Field(str, required=False, max_length=2000, nullable=True),
    }
)
def update_rating(rating_id):
    data = validated()
    if not data:
        raise ValidationException(details={"_body": "no_fields"})

    rating = _service.update_rating(
        actor=current_user(),
        rating_id=rating_id,
        data=data,
    )
    return success_response(rating.to_dict())


# === DELETE Rating ===
@bp.delete("/ratings/<int:rating_id>")
@require_role(Role.ADMIN)
def delete_rating(rating_id):
    _service.delete_rating(
        actor=current_user(),
        rating_id=rating_id,
    )
    return success_response(message="Xóa đánh giá thành công")
