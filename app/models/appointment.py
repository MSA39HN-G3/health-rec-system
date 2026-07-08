from datetime import datetime, timezone
from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class AppointmentStatusHistory(db.Model):
    """Bảng lưu trữ lịch sử thay đổi trạng thái của lịch hẹn (Audit log)."""

    __tablename__ = "appointment_status_history"

    id = db.Column(db.Integer, primary_key=True)
    # Lịch hẹn liên kết.
    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Trạng thái trước khi thay đổi.
    old_status = db.Column(db.String(32), nullable=True)
    # Trạng thái sau khi thay đổi.
    new_status = db.Column(db.String(32), nullable=False)
    # Người thực hiện thay đổi.
    changed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Ghi chú hoặc lý do thay đổi trạng thái.
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)

    changed_by_user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_by": self.changed_by,
            "changed_by_user": (
                {"id": self.changed_by_user.id, "full_name": self.changed_by_user.full_name}
                if self.changed_by_user
                else None
            ),
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Appointment(db.Model):
    """Bản ghi lịch hẹn khám hoàn chỉnh cuối cùng."""

    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    # Mã lịch hẹn duy nhất (vd 'APT-20260715-0042') dùng tra cứu.
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # Phiên đặt lịch liên kết (nếu có).
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("booking_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Bệnh nhân đặt lịch.
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Khoa được chọn khám.
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Bác sĩ phụ trách khám.
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Phòng khám thực hiện.
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Ca làm việc gốc của bác sĩ.
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey("doctor_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Ngày khám.
    appointment_date = db.Column(db.Date, nullable=False)
    # Giờ bắt đầu khám.
    start_time = db.Column(db.Time, nullable=False)
    # Giờ kết thúc khám.
    end_time = db.Column(db.Time, nullable=False)
    # Trạng thái lịch hẹn: pending | confirmed | checked_in | completed | cancelled | no_show.
    status = db.Column(
        db.String(32), nullable=False, default="pending", server_default="'pending'"
    )
    # Ghi chú triệu chứng tại thời điểm đặt.
    symptom_note = db.Column(db.Text)
    # Lý do hủy lịch (nếu có).
    cancel_reason = db.Column(db.Text)
    # Người tạo lịch hẹn (vd nhân viên y tế đặt hộ hoặc bệnh nhân).
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    session = db.relationship("BookingSession", backref=db.backref("appointment", uselist=False))
    patient = db.relationship("Patient", backref=db.backref("appointments", lazy="dynamic"))
    department = db.relationship("Department", backref=db.backref("appointments", lazy="dynamic"))
    doctor = db.relationship("Doctor", backref=db.backref("appointments", lazy="dynamic"))
    room = db.relationship("Room", backref=db.backref("appointments", lazy="dynamic"))
    schedule = db.relationship("DoctorSchedule", backref=db.backref("appointments", lazy="dynamic"))
    created_by_user = db.relationship(
        "User",
        foreign_keys=[created_by_user_id],
        backref=db.backref("created_appointments", lazy="dynamic"),
    )

    status_history = db.relationship(
        "AppointmentStatusHistory",
        backref=db.backref("appointment"),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("doctor_id", "appointment_date", "start_time", name="uq_appointments_doctor_slot"),
        db.CheckConstraint("end_time > start_time", name="check_appointments_time"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "patient": (
                {"id": self.patient.id, "full_name": self.patient.full_name}
                if self.patient
                else None
            ),
            "department_id": self.department_id,
            "department": (
                {"id": self.department.id, "name": self.department.name}
                if self.department
                else None
            ),
            "doctor_id": self.doctor_id,
            "doctor": (
                {"id": self.doctor.id, "full_name": self.doctor.full_name}
                if self.doctor
                else None
            ),
            "room_id": self.room_id,
            "room": (
                {"id": self.room.id, "name": self.room.name, "code": self.room.code}
                if self.room
                else None
            ),
            "schedule_id": self.schedule_id,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "symptom_note": self.symptom_note,
            "cancel_reason": self.cancel_reason,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
