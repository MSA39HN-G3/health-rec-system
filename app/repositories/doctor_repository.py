from ..extensions import db
from ..models.doctor import Doctor


class DoctorRepository:
    def find_by_id(self, doctor_id):
        return db.session.get(Doctor, doctor_id)

    def find_by_license_number(self, license_number):
        """Tìm bác sĩ theo số giấy phép hành nghề."""
        return Doctor.query.filter_by(license_number=license_number).first()

    def find_by_email(self, email):
        """Tìm bác sĩ theo email (so khớp không phân biệt hoa thường)."""
        from sqlalchemy import func

        normalized = (email or "").strip()
        if not normalized:
            return None
        return Doctor.query.filter(
            func.lower(Doctor.email) == normalized.lower()
        ).first()

    def paginate(self, page, size, department_id=None, is_active=None):
        """Lấy danh sách bác sĩ có phân trang.

        Nếu `department_id` được truyền vào, lọc theo đúng khoa đó.
        Kết quả sắp xếp theo `id` tăng dần để thứ tự ổn định giữa các trang.
        Trả về (items, total).
        """
        query = Doctor.query
        if department_id is not None:
            query = query.filter(Doctor.department_id == department_id)
        if is_active is not None:
            query = query.filter(Doctor.is_active == is_active)
        query = query.order_by(Doctor.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def search(self, keyword, page, size, department_id=None):
        """Tìm kiếm bác sĩ theo tên hoặc chuyên khoa.

        Args:
            keyword: Từ khóa tìm kiếm (sẽ được wrap với %% để LIKE)
            page: Số trang
            size: Số item/trang
            department_id: Lọc theo khoa (tùy chọn)

        Returns:
            tuple: (list of Doctor, total count)
        """
        query = Doctor.query
        if department_id is not None:
            query = query.filter(Doctor.department_id == department_id)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                db.or_(
                    Doctor.full_name.ilike(pattern),
                    Doctor.specialization.ilike(pattern),
                    Doctor.license_number.ilike(pattern),
                )
            )
        query = query.order_by(Doctor.id)
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return items, total

    def find_by_specialization(self, specialization):
        """Tìm tất cả bác sĩ theo chuyên khoa."""
        return Doctor.query.filter(
            Doctor.specialization.ilike(f"%{specialization}%"),
            Doctor.is_active == True,
        ).all()

    def find_expiring_licenses(self, days=30):
        """Tìm các bác sĩ có giấy phép sắp hết hạn trong N ngày."""
        from datetime import date
        future_date = date.today() + __import__("datetime").timedelta(days=days)
        return Doctor.query.filter(
            Doctor.license_expiry_date.isnot(None),
            Doctor.license_expiry_date <= future_date,
            Doctor.license_expiry_date >= date.today(),
        ).all()

    def add(self, doctor):
        db.session.add(doctor)
        return doctor

    def update(self, doctor):
        """Cập nhật doctor và commit."""
        db.session.add(doctor)
        db.session.commit()
        return doctor

    def delete(self, doctor):
        """Xóa bác sĩ (soft delete bằng cách set is_active=False)."""
        doctor.is_active = False
        db.session.commit()

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
