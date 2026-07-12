"""Service quản lý khoa/chuyên khoa (khu vực admin)."""
import logging

from sqlalchemy.exc import IntegrityError

from ..common.csv_export import build_csv
from ..common.csv_schemas import (
    doctor_column_keys,
    doctor_header_labels,
    format_doctor_row,
)
from ..errors import ConflictException, NotFoundException
from ..models.department import Department
from ..repositories.department_repository import DepartmentRepository

logger = logging.getLogger(__name__)

# Tiền tố mã chuyên khoa (vd "CK-001") và số lần thử lại khi đụng độ mã do tạo
# đồng thời (unique violation) trước khi bỏ cuộc.
_CODE_PREFIX = "CK-"
_MAX_CODE_RETRIES = 5

# Sentinel phân biệt "không truyền field" (giữ nguyên) với "truyền null" (xóa) khi
# cập nhật từng phần (PATCH).
_UNSET = object()


class DepartmentService:
    def __init__(self, department_repository=None):
        # Sau refactor 1a2b3c4d5e6f: bỏ head_doctor, không còn user/role repo.
        self.departments = department_repository or DepartmentRepository()

    def get_department(self, department_id):
        """Lấy thông tin 1 khoa. 404 nếu không thấy."""
        department = self.departments.find_by_id(department_id)
        if department is None:
            raise NotFoundException("errors.department_not_found")
        return department

    def list_department_doctors(
        self,
        department_id,
        page=1,
        size=10,
        q=None,
        qualification=None,
    ):
        """Lấy danh sách bác sĩ thuộc 1 khoa, kèm `stats` (snapshot trong 1 roundtrip).

        Trả về dict gồm:
          - `stats`: tổng/đang hoạt động/tạm ngưng + bệnh nhân đang điều trị hôm nay.
          - `doctors`: trang danh sách (theo `q` / `qualification`).
          - `total`: tổng số doctor khớp filter (để client tính totalPage).

        Mục đích: phục vụ màn "Chi tiết chuyên khoa" của FE — gộp stats + list
        vào cùng response (1 transaction, đảm bảo tính nhất quán snapshot).
        Xem `docs/FE_DEPARTMENT_DETAIL.md`.
        """
        department = self.departments.find_by_id(department_id)
        if department is None:
            raise NotFoundException("errors.department_not_found")

        # 1) Stats — 1 SQL duy nhất.
        total, active = self.departments.doctor_stats_by_status(department_id)
        treating = self.departments.treating_patients_today(department_id)

        # 2) Danh sách bác sĩ theo filter — repository đã hỗ trợ sẵn.
        items, list_total = self.departments.list_doctors_for_department(
            department_id,
            page=page,
            size=size,
            q=q,
            qualification=qualification,
        )

        return {
            "stats": {
                "total_doctors": total,
                "active_doctors": active,
                "inactive_doctors": max(total - active, 0),
                "treating_patients": treating,
            },
            "doctors": items,
            "total": list_total,
        }

    def list_departments(self, page, size):
        """Danh sách khoa phân trang. Trả về (items, total)."""
        return self.departments.paginate(page, size)

    # ------------------------------------------------------------------ #
    #  Export CSV (xem docs/FE_DEPARTMENT_DETAIL.md §5)                 #
    # ------------------------------------------------------------------ #

    # Ngưỡng cảnh báo: số bác sĩ vượt mức này sẽ khiến file CSV rất lớn. Có
    # thể raise / log; hiện tại chỉ dùng để metric, không chặn.
    EXPORT_ROW_WARN_LIMIT = 5_000

    def export_department_doctors_csv(
        self,
        department_id,
        q=None,
        qualification=None,
    ):
        """Sinh CSV chứa toàn bộ bác sĩ thuộc 1 khoa.

        Trả về tuple `(csv_text, department, total_rows)`:
          - `csv_text`: chuỗi CSV đã được escape đúng chuẩn RFC 4180, có BOM
            UTF-8 để Excel mở đúng tiếng Việt.
          - `department`: object Department (để controller dùng cho filename).
          - `total_rows`: số dòng dữ liệu (chưa tính header).

        Schema cột được khai báo tập trung ở `app.common.csv_schemas` (gom theo
        từng phần nghiệp vụ của Doctor: phần 1 cá nhân, phần 2 chuyên môn, phần 5
        hành chính). Mỗi cột có nhãn tiếng Việt + key EN trong ngoặc, date hiển
        thị dd/mm/yyyy, bool render "Có"/"Không".

        Field bị loại khỏi export (và lý do):
          - `avatar_url`, `avatar_object_key`: ảnh không cần trong bảng phẳng;
            nếu cần hiển thị FE có thể tự gọi presign GET kèm object_key.
          - `documents`, `statistics`: quan hệ nặng, không phù hợp bảng.
          - `department` (object): đã ngầm biết vì export theo khoa.
          - (Tính năng đánh giá đã bỏ ở refactor 1c2d3e4f5a6b nên không còn `ratings`.)
        """
        from ..models.doctor import Doctor  # noqa: F401  (giữ import để type-hint)

        department = self.departments.find_by_id(department_id)
        if department is None:
            raise NotFoundException("errors.department_not_found")

        doctors = self.departments.list_all_doctors_for_department(
            department_id, q=q, qualification=qualification
        )

        columns = doctor_column_keys()
        header_labels = doctor_header_labels()
        rows = [format_doctor_row(d.to_dict()) for d in doctors]

        csv_text = build_csv(columns, header_labels, rows)
        return csv_text, department, len(rows)

    def get_stats(self):
        """Thống kê số lượng khoa: tổng, đang hoạt động, tạm dừng."""
        total, active, inactive = self.departments.count_by_status()
        return {"total": total, "active": active, "inactive": inactive}

    def create_department(
        self,
        name,
        location=None,
        description=None,
        keywords=None,
        conditions=None,
        ai_metadata=None,
        is_active=False,
    ):
        # Sau refactor 1a2b3c4d5e6f: bỏ head_doctor_id và việc auto-grant role
        # staff kèm trưởng khoa. Staff giờ quản lý tất cả bác sĩ trong khoa nên
        # không cần "bổ nhiệm" trưởng khoa nữa. `is_active` do client quyết định
        # trực tiếp, mặc định False.

        # Sinh mã "CK-NNN" duy nhất do hệ thống cấp. Thử lại nếu đụng độ unique
        # do hai request tạo khoa cùng lúc cùng tính ra một số thứ tự.
        for _ in range(_MAX_CODE_RETRIES):
            department = Department(
                code=self._next_code(),
                name=name,
                location=location,
                description=description,
                keywords=keywords or [],
                conditions=conditions or [],
                ai_metadata=ai_metadata or {},
                is_active=is_active,
            )
            self.departments.add(department)

            try:
                # Commit 1 transaction cho cả tạo khoa.
                self.departments.commit()
                return department
            except IntegrityError:
                self.departments.rollback()

        # Hết số lần thử mà vẫn đụng độ -> coi như xung đột mã khoa.
        raise ConflictException("errors.department_code_exists")

    def update_department(
        self,
        department_id,
        *,
        name=_UNSET,
        location=_UNSET,
        avatar_url=_UNSET,
        avatar_object_key=_UNSET,
        description=_UNSET,
        keywords=_UNSET,
        conditions=_UNSET,
        techniques=_UNSET,
        ai_metadata=_UNSET,
        is_active=_UNSET,
    ):
        """Cập nhật từng phần một khoa. Chỉ các field được truyền mới thay đổi.

        Mã khoa (`code`) là cố định, không cho sửa. `head_doctor_id` đã bỏ theo
        refactor 1a2b3c4d5e6f — staff giờ quản lý tất cả bác sĩ trong khoa,
        không cần gắn một user/doctor cụ thể làm "trưởng".

        `avatar_object_key` được ưu tiên hơn `avatar_url`: khi set object_key
        thì cũng xoá cache URL cũ để buộc BE sinh lại presigned GET lần kế.
        Gửi null cho cả hai field đều xoá ảnh.
        """
        department = self.departments.find_by_id(department_id)
        if department is None:
            raise NotFoundException("errors.department_not_found")

        if name is not _UNSET:
            department.name = name
        if location is not _UNSET:
            department.location = location
        if avatar_url is not _UNSET:
            department.avatar_url = avatar_url
        if avatar_object_key is not _UNSET:
            # Snapshot key cũ TRƯỚC khi gán — dùng để xóa object trên R2
            # sau khi commit DB thành công (xem `self._cleanup_old_avatar`).
            old_object_key = department.avatar_object_key
            new_object_key = avatar_object_key

            department.avatar_object_key = new_object_key
            # Khi gán object_key mới hoặc xoá (None) thì cache URL cũ không
            # còn hợp lệ -> xoá để to_dict() tự derive lại presigned GET.
            department.avatar_url = None
        else:
            old_object_key = None
            new_object_key = None
        if description is not _UNSET:
            department.description = description
        if keywords is not _UNSET:
            department.keywords = keywords
        if conditions is not _UNSET:
            department.conditions = conditions
        if techniques is not _UNSET:
            department.techniques = techniques
        if ai_metadata is not _UNSET:
            department.ai_metadata = ai_metadata
        if is_active is not _UNSET:
            # FE có thể bật/tắt khoa trực tiếp (không còn ràng buộc với head_doctor).
            department.is_active = is_active

        self.departments.commit()
        # Cleanup R2 chạy SAU commit: nếu commit fail thì DB vẫn giữ key cũ,
        # R2 cũng còn file cũ -> dữ liệu nhất quán. Nếu commit OK mà xóa R2
        # lỗi thì chỉ tốn storage (orphan), không ảnh hưởng nghiệp vụ.
        self._cleanup_old_avatar(old_object_key, new_object_key)
        return department

    def _cleanup_old_avatar(self, old_key, new_key):
        """Xóa object avatar cũ trên R2 sau khi DB đã được commit thành công.

        An toàn với:
          - PATCH đổi sang key mới (`old_key != new_key`, cả 2 khác None).
          - PATCH xoá avatar (`new_key is None`, `old_key` còn giá trị).
          - PATCH set cùng key hiện tại (idempotent, không xóa).
        Lỗi R2 chỉ log warning — không raise, không rollback.
        """
        if not old_key or old_key == new_key:
            return
        # Import trong hàm để tránh import vòng (storage -> extensions).
        from botocore.exceptions import BotoCoreError, ClientError

        from .storage import delete_object

        try:
            delete_object(old_key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "Failed to delete old department avatar from R2: %s (key=%s)",
                exc,
                old_key,
            )

    def _next_code(self):
        """Mã chuyên khoa kế tiếp dạng `CK-NNN` (NNN >= 001, zero-pad 3 chữ số)."""
        return f"{_CODE_PREFIX}{self.departments.max_code_number(_CODE_PREFIX) + 1:03d}"

    # `_grant_department_head` đã bỏ theo refactor 1a2b3c4d5e6f — staff quản
    # lý tất cả bác sĩ nên không cần auto-grant role staff khi gán head_doctor.
