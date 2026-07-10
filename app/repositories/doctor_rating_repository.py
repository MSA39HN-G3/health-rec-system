"""Repository layer for DoctorRating model."""
from ..extensions import db
from ..models.doctor_rating import DoctorRating


class DoctorRatingRepository:
    def find_by_id(self, rating_id):
        return db.session.get(DoctorRating, rating_id)

    def find_by_doctor_id(self, doctor_id, page=None, size=None):
        """Lấy đánh giá của một bác sĩ.

        Args:
            doctor_id: ID của bác sĩ
            page: Số trang (tùy chọn)
            size: Số item/trang (tùy chọn)

        Returns:
            tuple: (list of DoctorRating, total count) hoặc list nếu không phân trang
        """
        query = DoctorRating.query.filter_by(doctor_id=doctor_id)
        query = query.order_by(DoctorRating.created_at.desc())
        if page is not None and size is not None:
            total = query.count()
            items = query.offset((page - 1) * size).limit(size).all()
            return items, total
        return query.all()

    def find_by_patient_id(self, patient_id):
        """Lấy đánh giá của một bệnh nhân đã từng đánh giá."""
        return DoctorRating.query.filter_by(patient_id=patient_id).all()

    def find_by_appointment_id(self, appointment_id):
        """Lấy đánh giá theo lịch hẹn (1 lịch hẹn chỉ có 1 đánh giá)."""
        return DoctorRating.query.filter_by(appointment_id=appointment_id).first()

    def has_rated_appointment(self, patient_id, appointment_id):
        """Kiểm tra bệnh nhân đã đánh giá lịch hẹn này chưa."""
        return DoctorRating.query.filter_by(
            patient_id=patient_id,
            appointment_id=appointment_id,
        ).first() is not None

    def get_doctor_average_rating(self, doctor_id):
        """Tính điểm đánh giá trung bình của bác sĩ.

        Returns:
            tuple: (average_rating, total_count) hoặc (None, 0) nếu chưa có đánh giá
        """
        ratings = DoctorRating.query.filter_by(doctor_id=doctor_id).all()
        if not ratings:
            return None, 0
        avg = sum(r.rating for r in ratings) / len(ratings)
        return round(avg, 2), len(ratings)

    def get_rating_distribution(self, doctor_id):
        """Lấy phân bố đánh giá theo số sao (1-5).

        Returns:
            dict: {1: count, 2: count, 3: count, 4: count, 5: count}
        """
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        ratings = DoctorRating.query.filter_by(doctor_id=doctor_id).all()
        for r in ratings:
            if r.rating in distribution:
                distribution[r.rating] += 1
        return distribution

    def add(self, rating):
        db.session.add(rating)
        db.session.commit()
        return rating

    def update(self, rating):
        db.session.add(rating)
        db.session.commit()
        return rating

    def delete(self, rating):
        db.session.delete(rating)
        db.session.commit()

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
