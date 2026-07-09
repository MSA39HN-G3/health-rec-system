from datetime import datetime, timezone
from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class AIRecommendation(db.Model):
    """Kết quả gợi ý chuyên khoa từ AI (gồm top 3 chuyên khoa gợi ý)."""

    __tablename__ = "ai_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    # Phiên đặt lịch liên kết.
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("booking_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Chuyên khoa được gợi ý.
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Thứ hạng gợi ý (1-3).
    rank = db.Column(db.Integer, nullable=False)
    # Điểm tin cậy (vd 0.4500).
    confidence_score = db.Column(db.Numeric(5, 4), nullable=False)
    # Giải thích lý do gợi ý của AI.
    reasoning = db.Column(db.Text)
    # Định danh model AI đã sử dụng.
    model_name = db.Column(
        db.String(255),
        nullable=False,
        default="ppr501.22-recommend",
        server_default="'ppr501.22-recommend'",
    )
    # Đánh dấu chuyên khoa được người dùng thực tế chọn.
    is_selected = db.Column(
        db.Boolean, default=False, nullable=False, server_default="false"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    session = db.relationship(
        "BookingSession", backref=db.backref("ai_recommendation_list", lazy="dynamic")
    )
    department = db.relationship(
        "Department", backref=db.backref("ai_recommendations", lazy="dynamic")
    )

    __table_args__ = (
        db.UniqueConstraint("session_id", "rank", name="uq_ai_recommendations_session_rank"),
        db.UniqueConstraint("session_id", "department_id", name="uq_ai_recommendations_session_dept"),
        db.CheckConstraint("rank BETWEEN 1 AND 3", name="check_ai_recommendations_rank"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "department_id": self.department_id,
            "department": (
                {"id": self.department.id, "name": self.department.name, "code": self.department.code}
                if self.department
                else None
            ),
            "rank": self.rank,
            "confidence_score": float(self.confidence_score) if self.confidence_score is not None else None,
            "reasoning": self.reasoning,
            "model_name": self.model_name,
            "is_selected": self.is_selected,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
