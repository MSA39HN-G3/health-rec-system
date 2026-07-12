"""Fixture dùng chung cho test.

Mỗi test chạy trong app context riêng. **KHÔNG** gọi `db.create_all()` ở
fixture `app` vì model `Department`/`Symptom` dùng ARRAY/JSONB (Postgres-only)
không tương thích SQLite. Test dùng mock repository (MagicMock) nên không cần
schema; test nào thật sự cần DB sẽ dùng fixture `db_sqlite` (xem bên dưới)
chỉ tạo table SQLite-compatible.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# ------------------------------------------------------------------
# Set env TRƯỚC khi import app.
# ------------------------------------------------------------------
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_EXPIRES", "3600")
os.environ.setdefault("JWT_REFRESH_EXPIRES", "1209600")  # 14 days
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost/cb")
os.environ.setdefault("R2_ACCOUNT_ID", "test-r2-account")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-r2-key")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-r2-secret")
os.environ.setdefault("R2_BUCKET", "test-bucket")
os.environ.setdefault("RATELIMIT_ENABLED", "false")


# Danh sách model SQLite-friendly (bỏ Department, Doctor, Symptom,
# SymptomCategory? — kiểm tra dưới).
_SQLITE_SAFE_TABLES = {
    "users", "roles", "permissions", "user_roles", "role_permissions",
    "oauth_states", "token_blacklist", "refresh_tokens",
    # SymptomCategory: dùng String/Integer, OK.
    "symptom_categories",
    # Bỏ "departments" (ARRAY/JSONB), "doctors" (FK tới departments → fail
    # cascade), "symptoms" (JSONB), "symptom_department_maps".
}


@pytest.fixture()
def app(monkeypatch):
    from app import create_app
    from app.extensions import db

    app = create_app("testing")

    with app.app_context():
        # KHÔNG gọi create_all() toàn bộ — một số model dùng Postgres ARRAY/JSONB.
        # Test nào cần DB thật phải opt-in qua fixture `db_sqlite`.
        yield app
        db.session.remove()


@pytest.fixture()
def db_sqlite(app):
    """Opt-in: tạo schema SQLite-friendly. Dùng cho test integration thật."""
    from app.extensions import db

    with app.app_context():
        # Chỉ tạo table an toàn với SQLite.
        for table in db.metadata.sorted_tables:
            if table.name in _SQLITE_SAFE_TABLES:
                table.create(db.engine, checkfirst=True)
        yield db
        for table in reversed(db.metadata.sorted_tables):
            if table.name in _SQLITE_SAFE_TABLES:
                table.drop(db.engine, checkfirst=True)
        db.session.remove()


# Alias `db` cho code cũ — không tạo schema.
@pytest.fixture()
def db(app):
    from app.extensions import db as _db
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


# ============================================================
# Factory: tạo Role / Permission / User trực tiếp (cần db_sqlite).
# ============================================================

@pytest.fixture()
def make_permission(db_sqlite):
    from app.models.rbac import Permission

    def _make(code, description=None):
        perm = Permission(name=code, description=description or code)
        db_sqlite.session.add(perm)
        db_sqlite.session.flush()
        return perm

    return _make


@pytest.fixture()
def make_role(db_sqlite, make_permission):
    from app.models.rbac import Role

    def _make(name, permission_codes=()):
        role = Role(name=name, description=name)
        for code in permission_codes:
            role.permissions.append(make_permission(code))
        db_sqlite.session.add(role)
        db_sqlite.session.flush()
        return role

    return _make


@pytest.fixture()
def make_user(db_sqlite):
    from app.models.user import User

    def _make(
        *,
        google_sub=None,
        email=None,
        full_name="Test User",
        is_active=True,
        roles=None,
        picture=None,
        email_verified=False,
    ):
        google_sub = google_sub or f"g-{email}"
        email = email or f"{google_sub}@test.local"
        user = User(
            google_sub=google_sub,
            email=email,
            full_name=full_name,
            is_active=is_active,
            picture=picture,
            email_verified=email_verified,
        )
        for role in roles or []:
            user.roles.append(role)
        db_sqlite.session.add(user)
        db_sqlite.session.flush()
        return user

    return _make


@pytest.fixture()
def admin_user(db_sqlite, make_role, make_user):
    role = make_role("admin", ["department:manage", "symptom:manage"])
    return make_user(
        google_sub="g-admin",
        email="admin@test.local",
        full_name="Admin",
        roles=[role],
    )


@pytest.fixture()
def dept_head_user(db_sqlite, make_role, make_user):
    """User kiêm trưởng khoa: trước đây tạo role `department_head`, sau refactor
    trở thành role `staff` (cùng tập permission cũ)."""
    role = make_role("staff", ["department:manage"])
    return make_user(
        google_sub="g-head",
        email="head@test.local",
        full_name="Head",
        roles=[role],
    )


@pytest.fixture()
def plain_user(db_sqlite, make_role, make_user):
    role = make_role("user", [])
    return make_user(
        google_sub="g-plain",
        email="plain@test.local",
        full_name="Plain",
        roles=[role],
    )


# ============================================================
# Token helpers
# ============================================================

@pytest.fixture()
def make_token(app):
    from app.services.token_service import issue_access_token

    def _make(user):
        token, jti, exp = issue_access_token(user)
        return token, jti, exp

    return _make


@pytest.fixture()
def auth_header(make_token):
    def _header(user):
        token, _, _ = make_token(user)
        return {"Authorization": f"Bearer {token}"}

    return _header


@pytest.fixture()
def make_refresh_token(app):
    """Phát refresh token thật (lưu DB) — dùng cho test refresh flow."""
    from app.services.refresh_token_service import RefreshTokenService

    def _make(user, **kwargs):
        with app.app_context():
            svc = RefreshTokenService()
            return svc.issue(user, **kwargs)

    return _make


# ============================================================
# Mock các dịch vụ ngoài
# ============================================================

@pytest.fixture()
def mock_external_services(monkeypatch):
    """Mock Google OAuth + Cloudflare R2."""
    from app.services import auth_service as _auth_mod
    from app.services import storage as _storage_mod

    google_exchange = MagicMock(
        return_value={
            "id_token": "fake.id.token",
            "access_token": "fake-access",
        }
    )
    presign_put = MagicMock(
        return_value={
            "method": "PUT",
            "url": "https://r2.test/bucket/key?X-Amz-Signature=abc",
            "headers": {"Content-Type": "image/png"},
            "expires_in": 600,
        }
    )
    presign_get = MagicMock(
        return_value="https://r2.test/bucket/key?X-Amz-Signature=xyz"
    )
    head_exists = MagicMock(return_value=True)
    delete_obj = MagicMock(return_value=True)

    monkeypatch.setattr(_auth_mod, "exchange_code_for_tokens", google_exchange)
    monkeypatch.setattr(
        _auth_mod, "verify_id_token",
        MagicMock(return_value={
            "sub": "g-test", "email": "test@test.local", "name": "Test User",
            "picture": None, "email_verified": True,
        }),
    )
    monkeypatch.setattr(_storage_mod, "presign_put", presign_put)
    monkeypatch.setattr(_storage_mod, "presign_get", presign_get)
    monkeypatch.setattr(_storage_mod, "head_exists", head_exists)
    monkeypatch.setattr(_storage_mod, "delete_object", delete_obj)

    return {
        "google_exchange": google_exchange,
        "presign_put": presign_put,
        "presign_get": presign_get,
        "head_exists": head_exists,
        "delete_obj": delete_obj,
    }


# ============================================================
# Time helpers
# ============================================================

@pytest.fixture()
def now_utc():
    return datetime.now(timezone.utc)


@pytest.fixture()
def future_dt():
    return datetime.now(timezone.utc) + timedelta(seconds=600)


@pytest.fixture()
def past_dt():
    return datetime.now(timezone.utc) - timedelta(seconds=600)
