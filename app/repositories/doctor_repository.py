from ..extensions import db
from ..models.doctor import Doctor


class DoctorRepository:
    def find_by_id(self, doctor_id):
        return db.session.get(Doctor, doctor_id)

    def paginate(self, page, size, department_id=None):
        """Lấy danh sách bác sĩ có phân trang.

        Nếu `department_id` được truyền vào, lọc theo đúng khoa đó. Kết quả sắp
        xếp theo `id` tăng dần để thứ tự ổn định giữa các trang. Trả về (items, total).
        """
        query = Doctor.query
        if department_id is not None:
            query = query.filter(Doctor.department_id == department_id)
        query = query.order_by(Doctor.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def add(self, doctor):
        db.session.add(doctor)
        return doctor

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
