"""Repository layer for DoctorStatistics model."""
from datetime import datetime, timezone
from ..extensions import db
from ..models.doctor_statistics import DoctorStatistics


def _now():
    return datetime.now(timezone.utc)


class DoctorStatisticsRepository:
    def find_by_id(self, stats_id):
        return db.session.get(DoctorStatistics, stats_id)

    def find_by_doctor_id(self, doctor_id):
        """Lấy thống kê của một bác sĩ."""
        return DoctorStatistics.query.filter_by(doctor_id=doctor_id).first()

    def find_or_create(self, doctor_id):
        """Lấy hoặc tạo mới thống kê cho bác sĩ."""
        stats = self.find_by_doctor_id(doctor_id)
        if not stats:
            stats = DoctorStatistics(doctor_id=doctor_id)
            db.session.add(stats)
            db.session.commit()
        return stats

    def get_top_rated(self, limit=10):
        """Lấy danh sách bác sĩ có điểm đánh giá cao nhất."""
        return (
            DoctorStatistics.query
            .filter(DoctorStatistics.average_rating.isnot(None))
            .order_by(DoctorStatistics.average_rating.desc())
            .limit(limit)
            .all()
        )

    def get_most_appointments(self, limit=10):
        """Lấy danh sách bác sĩ có nhiều lịch hẹn nhất."""
        return (
            DoctorStatistics.query
            .filter(DoctorStatistics.total_appointments > 0)
            .order_by(DoctorStatistics.total_appointments.desc())
            .limit(limit)
            .all()
        )

    def update(self, stats):
        stats.updated_at = _now()
        db.session.add(stats)
        db.session.commit()
        return stats

    def recalculate_for_doctor(self, doctor_id):
        """Tính lại toàn bộ thống kê cho một bác sĩ."""
        stats = self.find_or_create(doctor_id)

        from ..models.appointment import Appointment
        appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()

        stats.total_appointments = len(appointments)
        stats.completed_appointments = sum(1 for a in appointments if a.status == "completed")
        stats.cancelled_appointments = sum(1 for a in appointments if a.status == "cancelled")

        from ..models.doctor_rating import DoctorRating
        ratings = DoctorRating.query.filter_by(doctor_id=doctor_id).all()
        if ratings:
            stats.average_rating = round(sum(r.rating for r in ratings) / len(ratings), 2)
            stats.total_ratings = len(ratings)
        else:
            stats.average_rating = None
            stats.total_ratings = 0

        stats.last_calculated_at = _now()
        db.session.add(stats)
        db.session.commit()
        return stats

    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()
