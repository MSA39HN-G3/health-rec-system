"""Model DoctorStatistics - Thống kê hoạt động của bác sĩ.

Lưu trữ các chỉ số thống kê như số lượng lịch hẹn, thời gian khám TB.

Sau refactor 1c2d3e4f5a6b (bỏ tính năng đánh giá): các field liên quan rating
(``average_rating``, ``total_ratings``) và method ``recalculate_from_ratings``
đã được gỡ khỏi model.
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class DoctorStatistics(db.Model):
    __tablename__ = "doctor_statistics"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Thống kê lịch hẹn
    total_appointments = db.Column(db.Integer, default=0, nullable=False)
    completed_appointments = db.Column(db.Integer, default=0, nullable=False)
    cancelled_appointments = db.Column(db.Integer, default=0, nullable=False)
    # Thống kê thời gian
    average_consultation_time_minutes = db.Column(db.Integer)  # Thời gian khám TB (phút)
    patient_satisfaction_score = db.Column(db.Float)  # Điểm hài lòng (0-100)
    # Metadata
    last_calculated_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    @property
    def completion_rate(self):
        """Tỷ lệ hoàn thành lịch hẹn."""
        if self.total_appointments == 0:
            return 0.0
        return round(self.completed_appointments / self.total_appointments * 100, 2)

    @property
    def cancellation_rate(self):
        """Tỷ lệ hủy lịch hẹn."""
        if self.total_appointments == 0:
            return 0.0
        return round(self.cancelled_appointments / self.total_appointments * 100, 2)

    def recalculate_from_appointments(self):
        """Tính lại thống kê từ các lịch hẹn thực tế."""
        from ..models.appointment import Appointment

        appointments = Appointment.query.filter_by(doctor_id=self.doctor_id).all()

        self.total_appointments = len(appointments)
        self.completed_appointments = sum(1 for a in appointments if a.status == "completed")
        self.cancelled_appointments = sum(1 for a in appointments if a.status == "cancelled")
        self.last_calculated_at = _now()

    def to_dict(self):
        return {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "total_appointments": self.total_appointments,
            "completed_appointments": self.completed_appointments,
            "cancelled_appointments": self.cancelled_appointments,
            "completion_rate": self.completion_rate,
            "cancellation_rate": self.cancellation_rate,
            "average_consultation_time_minutes": self.average_consultation_time_minutes,
            "patient_satisfaction_score": self.patient_satisfaction_score,
            "last_calculated_at": self.last_calculated_at.isoformat() if self.last_calculated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
