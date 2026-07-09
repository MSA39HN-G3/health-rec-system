"""Model DoctorRating - Đánh giá bác sĩ từ bệnh nhân.

Lưu trữ đánh giá và nhận xét của bệnh nhân sau khi khám xong.
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class DoctorRating(db.Model):
    __tablename__ = "doctor_ratings"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating = db.Column(db.Integer, nullable=False)  # 1-5 sao
    comment = db.Column(db.Text)  # Nhận xét
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=True
    )

    # Relationships
    patient = db.relationship("Patient", backref=db.backref("doctor_ratings", lazy="dynamic"))
    appointment = db.relationship("Appointment", backref=db.backref("ratings", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("patient_id", "appointment_id", name="uq_doctor_rating_appointment"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "patient_id": self.patient_id,
            "patient": (
                {"id": self.patient.id, "full_name": self.patient.full_name}
                if self.patient
                else None
            ),
            "appointment_id": self.appointment_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
