from ..extensions import db
from ..models.department import Department


class DepartmentRepository:
    def find_by_id(self, department_id):
        return db.session.get(Department, department_id)

    def find_by_code(self, code):
        return Department.query.filter_by(code=code).first()

    def paginate(self, page, size):
        """Lấy danh sách khoa theo trang. Trả về (items, total)."""
        query = Department.query.order_by(Department.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, department):
        db.session.add(department)
        return department

    def commit(self):
        db.session.commit()
