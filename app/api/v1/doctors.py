"""Controller bác sĩ.

Hiện cung cấp 1 endpoint đọc:
  - GET /api/v1/doctors -> danh sách bác sĩ (phân trang, có phân quyền)

Phân quyền:
  - admin            -> thấy tất cả bác sĩ mọi khoa. Truyền `?department_id=` để
                       lọc thuận tiện.
  - department_head  -> chỉ thấy bác sĩ thuộc khoa user đó đang làm trưởng.
                       Nếu chưa là trưởng khoa nào -> 403.
"""
from flask import Blueprint

from ...common.response import paginated_response
from ...middleware import (
    Field,
    current_user,
    validate_query,
    validated_query,
)
from ...services.doctor_service import DoctorService

bp = Blueprint("doctors", __name__, url_prefix="/api/v1/doctors")

_service = DoctorService()


@bp.get("")
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
        # Admin có thể truyền để lọc theo khoa; department_head bị bỏ qua nếu khác
        # khoa của mình (service raise 403).
        "department_id": Field(int, required=False, minimum=1),
    }
)
def list_doctors():
    q = validated_query()
    items, total, scope = _service.list_doctors(
        actor=current_user(),
        page=q["page"],
        size=q["size"],
        department_id=q.get("department_id"),
    )
    return paginated_response(
        [d.to_dict() for d in items],
        page=q["page"],
        size=q["size"],
        total=total,
        # Trả kèm scope để client (FE) biết đang xem danh sách của phạm vi nào.
        message=scope["label"],
    )
