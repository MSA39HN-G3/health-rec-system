from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Symptom(db.Model):
    __tablename__ = "symptoms"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("symptom_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    synonyms = db.Column(JSONB, nullable=False, default=lambda: [])
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    category = db.relationship("SymptomCategory", back_populates="symptoms")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category.to_dict() if self.category else None,
            "synonyms": self.synonyms or [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
