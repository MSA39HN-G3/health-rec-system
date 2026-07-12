"""Entity Doctor - bác sĩ của hệ thống.

Tách khỏi User vì user là tài khoản đăng nhập, còn doctor là hồ sơ chuyên môn.
Một department có nhiều doctor thuộc khoa đó (qua doctor.department_id).
Khái niệm "trưởng khoa" cũ (head_doctor_id tham chiếu tới user/doctor cụ
thể) đã được bỏ — staff giờ quản lý tất cả bác sĩ trong khoa (xem migration
1a2b3c4d5e6f).
"""
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import ARRAY

from ..extensions import db


def _now():
    return datetime.now(timezone.utc)


class Doctor(db.Model):
    __tablename__ = "doctors"

    # === Core fields (existing) ===
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(64))
    is_active = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )
    created_at = db.Column(db.DateTime(timezone=True), default=_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # === Relationships ===
    department = db.relationship("Department", backref=db.backref("doctors", lazy="dynamic"))

    # === Phần 1: Thông tin cá nhân cơ bản ===
    phone = db.Column(db.String(32))
    email = db.Column(db.String(255))
    avatar_object_key = db.Column(db.String(512))
    avatar_url = db.Column(db.String(512))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(32))  # male, female, other
    address = db.Column(db.Text)

    # === Phần 2: Thông tin chuyên môn ===
    license_number = db.Column(db.String(64))  # Số giấy phép hành nghề
    license_issue_date = db.Column(db.Date)  # Ngày cấp giấy phép
    license_expiry_date = db.Column(db.Date)  # Ngày hết hạn giấy phép
    specialization = db.Column(db.String(255))  # Chuyên khoa chính
    sub_specializations = db.Column(ARRAY(db.String(255)), server_default="{}")
    education = db.Column(ARRAY(db.String(255)), server_default="{}")  # Trình độ học vấn
    experience_years = db.Column(db.Integer)  # Số năm kinh nghiệm
    training_institutions = db.Column(ARRAY(db.String(255)), server_default="{}")  # Nơi đào tạo

    # === Phần 5: Thông tin hành chính ===
    employment_type = db.Column(db.String(32))  # full_time, part_time, contract
    hire_date = db.Column(db.Date)  # Ngày vào làm
    contract_end_date = db.Column(db.Date)  # Ngày kết thúc hợp đồng
    is_accepting_new_patients = db.Column(
        db.Boolean, default=True, nullable=False, server_default="true"
    )

    # === Phần 6: Tài liệu (backref from DoctorDocument) ===
    documents = db.relationship(
        "DoctorDocument",
        backref="doctor",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # === Phần 7: Thống kê (đánh giá đã bỏ ở refactor 1c2d3e4f5a6b) ===
    statistics = db.relationship(
        "DoctorStatistics",
        backref="doctor",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def _get_avatar_url(self):
        """Lấy avatar URL, ưu tiên cache URL hoặc generate presigned."""
        from ..services.storage import presign_get

        avatar_key = self.avatar_object_key
        if not self.avatar_url and avatar_key:
            try:
                self.avatar_url = presign_get(avatar_key)
            except Exception:
                self.avatar_url = None
        return self.avatar_url

    def to_dict(self, include_stats=False):
        result = {
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
            # Phần 1: Thông tin cá nhân
            "phone": self.phone,
            "email": self.email,
            "avatar_object_key": self.avatar_object_key,
            "avatar_url": self._get_avatar_url(),
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender": self.gender,
            "address": self.address,
            # Phần 2: Thông tin chuyên môn
            "license_number": self.license_number,
            "license_issue_date": self.license_issue_date.isoformat() if self.license_issue_date else None,
            "license_expiry_date": self.license_expiry_date.isoformat() if self.license_expiry_date else None,
            "specialization": self.specialization,
            "sub_specializations": list(self.sub_specializations or []),
            "education": list(self.education or []),
            "experience_years": self.experience_years,
            "training_institutions": list(self.training_institutions or []),
            # Phần 5: Thông tin hành chính
            "employment_type": self.employment_type,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
            "contract_end_date": self.contract_end_date.isoformat() if self.contract_end_date else None,
            "is_accepting_new_patients": self.is_accepting_new_patients,
        }
        if include_stats and self.statistics:
            result["statistics"] = self.statistics.to_dict()
        return result

    def is_license_expiring_soon(self, days=30):
        """Kiểm tra giấy phép có sắp hết hạn không."""
        if not self.license_expiry_date:
            return False
        from datetime import date
        expiry = self.license_expiry_date
        return (expiry - date.today()).days <= days
