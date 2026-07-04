"""Chứa các fixture dùng chung cho mọi test.

Mỗi test chạy trong app context riêng + DB in-memory SQLite.
Các service gắn liền với Google OAuth / R2 được monkey-patch
qua fixture `mock_external_services`.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

# Trước khi import app phải đặt env test để app.config sinh đúng CORS/JWT secret.
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_EXPIRES", "3600")
# Tên biến phải khớp với các os.getenv(...) trong app/config.py.
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost/cb")
os.environ.setdefault("R2_ACCOUNT_ID", "test-r2-account")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-r2-key")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-r2-secret")
os.environ.setdefault("R2_BUCKET", "test-bucket")
os.environ.setdefault(
    "R2_ENDPOINT", "https://test.r2.cloudflarestorage.com"
)
# Tắt rate limit trong test (dù TestingConfig đã tắt, set lại cho chắc).
os.environ.setdefault("RATELIMIT_ENABLED", "false")


@pytest.fixture(scope="session")
def _config_test_db():
    """Buộc app dùng SQLite in-memory cho toàn session."""
    os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    return True


@pytest.fixture()
def app(_config_test_db, monkeypatch):
    """Tạo Flask app mới cho mỗi test, kèm DB sạch (drop & create)."""
    # Import trong fixture để env đã được set.
    from app import create_app
    from app.extensions import db

    app = create_app("testing")

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    """DB session, có sẵn app context."""
    from app.extensions import db as _db

    return _db


# ---------- Fixtures về user / role / permission ----------

@pytest.fixture()
def admin_user(db):
    """Tạo user + role admin (full permissions)."""
    from app.common.roles import RoleName
    from app.repositories import role_repository, user_repository
    from app.models.rbac import Role, Permission as PermModel

    # Tạo permission test nếu chưa có (an toàn vì test DB sạch).
    perm_manage_dept = PermModel(
        code="department:manage", description="manage departments"
    )
    perm_manage_sym = PermModel(code="symptom:manage", description="manage symptoms")
    db.session.add_all([perm_manage_dept, perm_manage_sym])
    db.session.flush()

    role = role_repository.create(
        name=RoleName.ADMIN.value,
        description="admin role",
        permission_codes=[
            "department:manage",
            "symptom:manage",
            "doctor:read",
            "user:read",
        ],
    )

    user = user_repository.create(
        email="admin@test.local",
        name="Admin Test",
        google_sub="g-admin",
        role_id=role.id,
        is_new=False,
    )
    db.session.commit()
    return user


@pytest.fixture()
def dept_head_user(db):
    """User với role department_head (chỉ có department:manage)."""
    from app.common.roles import RoleName
    from app.repositories import role_repository, user_repository
    from app.models.rbac import Role, Permission as PermModel

    PermModel(code="department:manage", description="manage departments")
    db.session.flush()

    role = role_repository.create(
        name=RoleName.DEPARTMENT_HEAD.value,
        description="dept head",
        permission_codes=["department:manage"],
    )
    user = user_repository.create(
        email="depthead@test.local",
        name="Dept Head Test",
        google_sub="g-head",
        role_id=role.id,
        is_new=False,
    )
    db.session.commit()
    return user


@pytest.fixture()
def plain_user(db):
    """User thường, không có permission quản lý gì."""
    from app.common.roles import RoleName
    from app.repositories import role_repository, user_repository

    role = role_repository.create(
        name=RoleName.USER.value,
        description="plain user",
        permission_codes=[],
    )
    user = user_repository.create(
        email="user@test.local",
        name="Plain User",
        google_sub="g-user",
        role_id=role.id,
        is_new=False,
    )
    db.session.commit()
    return user


# ---------- Helper: cấp token cho user bất kỳ ----------

@pytest.fixture()
def make_token(app):
    """Factory sinh access_token cho user bất kỳ (qua auth_service thật)."""
    from app.services.auth_service import AuthService

    svc = AuthService()

    def _make(user) -> tuple[str, Any]:
        token, exp = svc.issue_token(user)
        return token, exp

    return _make


@pytest.fixture()
def auth_header(make_token):
    """Factory trả header Authorization sẵn cho từng loại user."""

    def _header(user) -> dict[str, str]:
        token, _ = make_token(user)
        return {"Authorization": f"Bearer {token}"}

    return _header


# ---------- Mock các dịch vụ ngoài (Google OAuth + R2) ----------

@pytest.fixture()
def mock_external_services(monkeypatch):
    """Mock Google OAuth + Cloudflare R2 để test không phụ thuộc mạng/key thật.

    Trả về dict chứa các mock để test có thể điều chỉnh giá trị trả về.
    """
    mocks = {
        "google_exchange": MagicMock(
            return_value={
                "sub": "g-test",
                "email": "test@test.local",
                "name": "Test User",
                "picture": None,
            }
        ),
        "presign_put": MagicMock(
            return_value={
                "method": "PUT",
                "url": "https://test.r2.cloudflarestorage.com/test-bucket/avatar/test.png?X-Amz-Signature=abc",
                "headers": {"Content-Type": "image/png"},
                "expires_in": 900,
            }
        ),
        "presign_get": MagicMock(
            return_value={
                "url": "https://test.r2.cloudflarestorage.com/test-bucket/avatar/test.png?X-Amz-Signature=xyz",
                "expires_in": 3600,
            }
        ),
        "head_exists": MagicMock(return_value=True),
    }

    # Patch trong module services/auth_service và services/storage
    from app.services import auth_service as _auth_mod
    from app.services import storage as _storage_mod

    monkeypatch.setattr(_auth_mod, "exchange_google_code", mocks["google_exchange"])
    monkeypatch.setattr(_storage_mod, "presign_put", mocks["presign_put"])
    monkeypatch.setattr(_storage_mod, "presign_get", mocks["presign_get"])
    monkeypatch.setattr(_storage_mod, "head_exists", mocks["head_exists"])

    return mocks
