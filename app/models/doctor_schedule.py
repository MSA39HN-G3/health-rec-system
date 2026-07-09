from datetime import datetime, timezone
from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class DoctorSchedule(db.Model):
    """Lịch làm việc của bác sĩ lặp theo tuần tại một phòng cụ thể.

    Dùng để sinh động các khung giờ khám trống (slots).
    """

    __tablename__ = "doctor_schedules"

    id = db.Column(db.Integer, primary_key=True)
    # Bác sĩ làm việc.
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Phòng khám vật lý.
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Thứ trong tuần (0 = Chủ nhật, 1 = Thứ 2, ..., 6 = Thứ 7).
    day_of_week = db.Column(db.Integer, nullable=False)
    # Giờ bắt đầu ca làm việc.
    start_time = db.Column(db.Time, nullable=False)
    # Giờ kết thúc ca làm việc.
    end_time = db.Column(db.Time, nullable=False)
    # Độ dài một slot khám (mặc định 30 phút).
    slot_duration_minutes = db.Column(
        db.Integer, nullable=False, default=30, server_default="30"
    )
    # Số bệnh nhân tối đa trên mỗi slot.
    max_patients_per_slot = db.Column(
        db.Integer, nullable=False, default=1, server_default="1"
    )
    # Ngày bắt đầu lịch có hiệu lực.
    effective_from = db.Column(db.Date, nullable=True)
    # Ngày kết thúc lịch có hiệu lực (NULL = vô thời hạn).
    effective_to = db.Column(db.Date, nullable=True)
    is_active = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    doctor = db.relationship("Doctor", backref=db.backref("schedules", lazy="dynamic"))
    room = db.relationship("Room", backref=db.backref("schedules", lazy="dynamic"))

    __table_args__ = (
        db.CheckConstraint("end_time > start_time", name="check_doctor_schedules_time"),
    )

    def to_dict(self):
        return {
            "id": self.id,
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
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "slot_duration_minutes": self.slot_duration_minutes,
            "max_patients_per_slot": self.max_patients_per_slot,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
