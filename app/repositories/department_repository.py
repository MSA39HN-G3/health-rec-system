from ..extensions import db
from ..models.department import Department


class DepartmentRepository:
    def find_by_id(self, department_id):
        return db.session.get(Department, department_id)

    def find_by_code(self, code):
        return Department.query.filter_by(code=code).first()

    def find_by_name(self, name):
        return Department.query.filter_by(name=name).first()

    def find_by_head_doctor_id(self, user_id):
        """Khoa mà user đang là trưởng khoa (None nếu không phụ trách khoa nào)."""
        return (
            Department.query.filter_by(head_doctor_id=user_id)
            .order_by(Department.id)
            .first()
        )

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

    def add(self, department):
        db.session.add(department)
        return department

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
