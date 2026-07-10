from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class HealthRecordSymptom(db.Model):
    """Bảng trung gian N-N lưu trữ các triệu chứng trong hồ sơ sức khỏe."""

    __tablename__ = "health_record_symptoms"

    health_record_id = db.Column(
        db.Integer,
        db.ForeignKey("health_records.id", ondelete="CASCADE"),
        primary_key=True,
    )
    symptom_id = db.Column(
        db.BigInteger,
        db.ForeignKey("symptoms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)


class HealthRecord(db.Model):
    __tablename__ = "health_records"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visit_date = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    treatment = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    doctor = db.relationship("User", lazy="joined")
    department = db.relationship("Department", lazy="joined")

    symptoms = db.relationship(
        "Symptom",
        secondary="health_record_symptoms",
        backref=db.backref("health_records", lazy="dynamic"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "doctor": {
                "id": self.doctor.id,
                "full_name": self.doctor.full_name,
            }
            if self.doctor
            else None,
            "department_id": self.department_id,
            "department": {
                "id": self.department.id,
                "name": self.department.name,
                "code": self.department.code,
            }
            if self.department
            else None,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "title": self.title,
            "notes": self.notes,
            "diagnosis": self.diagnosis,
            "treatment": self.treatment,
            "symptoms": [s.to_dict() for s in self.symptoms] if self.symptoms else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
