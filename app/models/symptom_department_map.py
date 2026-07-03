from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class SymptomDepartmentMap(db.Model):
    """Ánh xạ triệu chứng → chuyên khoa kèm trọng số.

    weight càng cao thì triệu chứng này càng đặc trưng cho chuyên khoa đó.
    Dùng làm đầu vào cho engine gợi ý chuyên khoa.
    """

    __tablename__ = "symptom_department_map"
    __table_args__ = (
        db.UniqueConstraint("symptom_id", "department_id", name="uq_symptom_department"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    symptom_id = db.Column(
        db.BigInteger,
        db.ForeignKey("symptoms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weight = db.Column(db.Numeric(5, 2), nullable=False, default=1.0)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    symptom = db.relationship("Symptom", back_populates="department_mappings")
    department = db.relationship("Department", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "symptom_id": self.symptom_id,
            "department_id": self.department_id,
            "department": (
                {"id": self.department.id, "code": self.department.code, "name": self.department.name}
                if self.department
                else None
            ),
            "weight": float(self.weight),
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
