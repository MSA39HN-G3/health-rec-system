from ..extensions import db
from ..models.department import Department


class DepartmentRepository:
    def find_by_id(self, department_id):
        return db.session.get(Department, department_id)

    def find_by_code(self, code):
        return Department.query.filter_by(code=code).first()

    def find_by_name(self, name):
        return Department.query.filter_by(name=name).first()

    def max_code_number(self, prefix="CK-"):
        """Số thứ tự lớn nhất trong các mã dạng `prefix + NNN`. Trả 0 nếu chưa có.

        Quét mọi mã bắt đầu bằng prefix và lấy phần hậu tố số lớn nhất, nhờ đó
        mã kế tiếp luôn lớn hơn mọi mã hiện có (tránh đụng độ kể cả khi có
        khoảng trống do xóa).
        """
        rows = (
            Department.query.with_entities(Department.code)
            .filter(Department.code.like(f"{prefix}%"))
            .all()
        )
        max_n = 0
        for (code,) in rows:
            suffix = code[len(prefix):]
            if suffix.isdigit():
                max_n = max(max_n, int(suffix))
        return max_n

    def count_by_status(self):
        """Đếm số khoa theo trạng thái trong 1 truy vấn. Trả (total, active, inactive)."""
        rows = (
            db.session.query(Department.is_active, db.func.count(Department.id))
            .group_by(Department.is_active)
            .all()
        )
        active = inactive = 0
        for is_active, n in rows:
            if is_active:
                active = n
            else:
                inactive = n
        return active + inactive, active, inactive

    def paginate(self, page, size):
        """Lấy danh sách khoa theo trang. Trả về (items, total)."""
        query = Department.query.order_by(Department.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def find_all_active(self):
        """Lấy tất cả các khoa đang hoạt động."""
        return Department.query.filter_by(is_active=True).all()

    def find_all(self):
        """Lấy tất cả các khoa trong hệ thống."""
        return Department.query.all()

    # ------------------------------------------------------------------ #
    #  Stats + danh sách bác sĩ trực thuộc (phục vụ FE_DEPARTMENT_DETAIL) #
    # ------------------------------------------------------------------ #

    def doctor_stats_by_status(self, department_id):
        """Đếm số bác sĩ thuộc khoa theo `is_active`. Trả về (total, active)."""
        from ..models.doctor import Doctor

        rows = (
            db.session.query(Doctor.is_active, db.func.count(Doctor.id))
            .filter(Doctor.department_id == department_id)
            .group_by(Doctor.is_active)
            .all()
        )
        total = 0
        active = 0
        for is_active, n in rows:
            total += n
            if is_active:
                active = n
        return total, active

    def treating_patients_today(self, department_id):
        """Số bệnh nhân **đang được điều trị** bởi các bác sĩ trong khoa hôm nay.

        Quy tắc (xem FE_DEPARTMENT_DETAIL.md §3.4):
          - `appointment_date = today`
          - `status IN ('checked_in', 'in_session')` (fallback về `checked_in`
            nếu hệ thống chưa có trạng thái `in_session`).
          - `DISTINCT patient_id` để 1 bệnh nhân có nhiều appointment chỉ tính 1.
        """
        from datetime import date

        from ..models.appointment import Appointment

        statuses = ("checked_in", "in_session")
        # Không query trực tiếp status IN ('checked_in', 'in_session') vì DB có
        # thể chưa có `in_session`. Để an toàn, dùng 1 truy vấn OR 2 status.
        # Phòng trường hợp cột status chưa có giá trị `in_session`, DB vẫn chấp
        # nhận vì đây là string field không có enum check.
        return (
            db.session.query(db.func.count(db.func.distinct(Appointment.patient_id)))
            .filter(Appointment.department_id == department_id)
            .filter(Appointment.appointment_date == date.today())
            .filter(Appointment.status.in_(statuses))
            .scalar()
            or 0
        )

    def list_doctors_for_department(
        self,
        department_id,
        page=1,
        size=10,
        q=None,
        qualification=None,
    ):
        """Danh sách bác sĩ thuộc khoa với filter `q` (full_name) + `qualification`.

        Trả về (items, total). `qualification` được match LIKE %x% vào `title`.
        Sắp xếp theo `experience_years DESC NULLS LAST` (bác sĩ giàu kinh nghiệm
        hiển thị trước — phù hợp màn chi tiết khoa).
        """
        from ..models.doctor import Doctor

        query = Doctor.query.filter(Doctor.department_id == department_id)
        if q:
            pattern = f"%{q}%"
            query = query.filter(Doctor.full_name.ilike(pattern))
        if qualification:
            query = query.filter(Doctor.title.ilike(f"%{qualification}%"))
        # SQLite không hỗ trợ NULLS LAST -> dùng `coalesce(..., -1)` rồi DESC.
        query = query.order_by(
            db.func.coalesce(Doctor.experience_years, -1).desc(), Doctor.id
        )
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def list_all_doctors_for_department(
        self, department_id, q=None, qualification=None
    ):
        """Lấy TOÀN BỘ bác sĩ thuộc khoa (không phân trang) — dùng cho export CSV.

        Trả về list (không phải tuple). KHÔNG giới hạn số lượng: caller/service
        chịu trách nhiệm cảnh báo khi số lượng quá lớn (xem
        `DepartmentService.export_department_doctors_csv`).
        Sắp xếp giống `list_doctors_for_department` để thứ tự nhất quán.
        """
        from ..models.doctor import Doctor

        query = Doctor.query.filter(Doctor.department_id == department_id)
        if q:
            pattern = f"%{q}%"
            query = query.filter(Doctor.full_name.ilike(pattern))
        if qualification:
            query = query.filter(Doctor.title.ilike(f"%{qualification}%"))
        query = query.order_by(
            db.func.coalesce(Doctor.experience_years, -1).desc(), Doctor.id
        )
        return query.all()

    def add(self, department):
        db.session.add(department)
        return department

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
