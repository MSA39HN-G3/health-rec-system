from datetime import datetime, timezone
from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class BookingSessionSymptom(db.Model):
    """Bảng trung gian N-N lưu trữ các triệu chứng được chọn trong phiên đặt khám."""

    __tablename__ = "booking_session_symptoms"

    session_id = db.Column(
        db.String(36),
        db.ForeignKey("booking_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    symptom_id = db.Column(
        db.BigInteger,
        db.ForeignKey("symptoms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)


class BookingSession(db.Model):
    """Phiên đặt lịch khám lưu vết tiến trình 3 bước của bệnh nhân."""

    __tablename__ = "booking_sessions"

    id = db.Column(db.String(36), primary_key=True)  # session_id (UUID string)
    # Bệnh nhân thực hiện đặt lịch (NULL ở Bước 1, cập nhật ở Bước 2).
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Người thực hiện phiên đặt (vd tài khoản người dùng, lễ tân đặt hộ).
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Trạng thái chi tiết:
    # CREATED | PATIENT_INFO_COMPLETED | AI_RECOMMENDED | DEPARTMENT_SELECTED | ROOM_SELECTED | DOCTOR_SELECTED | BOOKED | CANCELLED
    status = db.Column(
        db.String(64), nullable=False, default="CREATED", server_default="'CREATED'"
    )
    # Bước hiện tại (1, 2, 3) để thống kê funnel.
    current_step = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    # Triệu chứng tự mô tả (free text).
    free_text_symptom = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    patient = db.relationship("Patient", backref=db.backref("booking_sessions", lazy="dynamic"))
    created_by_user = db.relationship("User", backref=db.backref("created_booking_sessions", lazy="dynamic"))

    # Danh sách triệu chứng có cấu trúc được chọn trong phiên
    symptoms = db.relationship(
        "Symptom",
        secondary="booking_session_symptoms",
        backref=db.backref("booking_sessions", lazy="dynamic"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient": (
                {"id": self.patient.id, "full_name": self.patient.full_name}
                if self.patient
                else None
            ),
            "created_by_user_id": self.created_by_user_id,
            "status": self.status,
            "current_step": self.current_step,
            "free_text_symptom": self.free_text_symptom,
            "symptoms": [s.to_dict() for s in self.symptoms] if self.symptoms else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
