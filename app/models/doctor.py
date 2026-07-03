"""Entity Doctor — bác sĩ của hệ thống.

Tách khỏi User vì user là tài khoản đăng nhập, còn doctor là hồ sơ chuyên môn.
Một department có một trưởng khoa (head_doctor trên Department) và nhiều doctor
thuộc khoa đó (qua doctor.department_id).
"""
from datetime import datetime, timezone

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    # Họ tên hiển thị của bác sĩ.
    full_name = db.Column(db.String(255), nullable=False)
    # Khoa mà bác sĩ trực thuộc. Bắt buộc (mọi bác sĩ phải thuộc một khoa).
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Chức danh chuyên môn (vd "Bác sĩ", "Thạc sĩ", "Tiến sĩ", "Phó khoa"...).
    title = db.Column(db.String(64))
    # Trạng thái hoạt động. False = tạm ngưng nhận lịch/khám.
    is_active = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    department = db.relationship("Department", backref=db.backref("doctors", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "department_id": self.department_id,
            "department": (
                {"id": self.department.id, "name": self.department.name, "code": self.department.code}
                if self.department
                else None
            ),
            "title": self.title,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
