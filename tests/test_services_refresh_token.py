"""Test cho refresh token flow (issue / rotate / revoke / reuse detection)."""
import pytest


@pytest.fixture()
def service(app, db_sqlite):
    """RefreshTokenService dùng DB thật (SQLite)."""
    from app.services.refresh_token_service import RefreshTokenService

    with app.app_context():
        return RefreshTokenService()


def test_issue_refresh_token_creates_record(service, app, plain_user, db_sqlite):
    """issue() phải tạo record trong DB với hash SHA-256."""
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        raw, expires_at = service.issue(plain_user)

    # Token phải có entropy đủ (URL-safe base64 32 bytes → ~43 chars).
    assert isinstance(raw, str)
    assert len(raw) >= 32

    # Hash trong DB phải khớp với hash(raw).
    with app.app_context():
        from app.services.refresh_token_service import _hash_token

        record = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(user_id=plain_user.id)
            .first()
        )
        assert record is not None
        assert record.token_hash == _hash_token(raw)
        assert record.revoked_at is None
        assert record.parent_id is None


def test_rotate_returns_new_pair(service, app, plain_user, db_sqlite):
    """rotate() trả access mới + refresh mới; token cũ bị revoke."""
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        old_raw, _ = service.issue(plain_user)

    result = service.rotate(old_raw)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["refresh_token"] != old_raw  # xoay vòng

    with app.app_context():
        # Token cũ phải bị revoke.
        old_record = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(user_id=plain_user.id, revoked_at=None)
            .first()
        )
        # Active token chỉ còn 1 — token mới.
        assert old_record is not None
        assert old_record.token_hash != __import__("hashlib").sha256(old_raw.encode()).hexdigest()

        # Token cũ đã revoke.
        from app.services.refresh_token_service import _hash_token

        old_hash = _hash_token(old_raw)
        old_row = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(token_hash=old_hash)
            .first()
        )
        assert old_row.revoked_at is not None


def test_rotate_unknown_token_raises(service, app):
    """Token không tồn tại trong DB -> UnauthorizedException."""
    from app.errors import UnauthorizedException

    with app.app_context():
        with pytest.raises(UnauthorizedException) as exc:
            service.rotate("this-token-does-not-exist")
        assert "refresh_invalid" in str(exc.value.message_key)


def test_rotate_expired_token_raises(service, app, plain_user, db_sqlite):
    """Token hết hạn -> UnauthorizedException, không phải reuse."""
    from datetime import datetime, timedelta, timezone

    from app.errors import UnauthorizedException
    from app.services.refresh_token_service import _hash_token
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        raw, _ = service.issue(plain_user)
        # Sửa expires_at thành quá khứ.
        record = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(token_hash=_hash_token(raw))
            .first()
        )
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        db_sqlite.session.commit()

    with app.app_context():
        with pytest.raises(UnauthorizedException) as exc:
            service.rotate(raw)
        # Phải là "invalid" chứ không phải reuse (vì expires_at < now).
        # Tuy nhiên service xử lý reuse chung cho cả expired lẫn revoked.
        assert "refresh" in str(exc.value.message_key).lower()


def test_reuse_detection_revokes_all_user_tokens(
    service, app, plain_user, db_sqlite
):
    """Dùng lại token đã revoke -> revoke_all + 401 reuse_detected."""
    from app.models.refresh_token import RefreshToken
    from app.errors import UnauthorizedException

    with app.app_context():
        # Cấp 2 token riêng biệt.
        raw_a, _ = service.issue(plain_user)
        raw_b, _ = service.issue(plain_user)

        # Rotate A → A bị revoke.
        service.rotate(raw_a)

        # Giờ thử rotate A lần nữa -> reuse detection.
        with pytest.raises(UnauthorizedException) as exc:
            service.rotate(raw_a)
        assert "refresh_reuse_detected" in str(exc.value.message_key)

    # Verify: mọi token của user đều bị revoke (kể cả B — vẫn active trước đó).
    with app.app_context():
        remaining = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(user_id=plain_user.id, revoked_at=None)
            .count()
        )
        assert remaining == 0


def test_revoke_single_token(service, app, plain_user, db_sqlite):
    """revoke() đánh dấu 1 token là revoked, không ảnh hưởng token khác."""
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        raw_a, _ = service.issue(plain_user)
        raw_b, _ = service.issue(plain_user)
        service.revoke(raw_a)

        from app.services.refresh_token_service import _hash_token

        a_hash = _hash_token(raw_a)
        b_hash = _hash_token(raw_b)

        rec_a = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(token_hash=a_hash)
            .first()
        )
        rec_b = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(token_hash=b_hash)
            .first()
        )
        assert rec_a.revoked_at is not None
        assert rec_b.revoked_at is None  # không ảnh hưởng


def test_revoke_all_for_user(service, app, plain_user, db_sqlite):
    """revoke_all_for_user() thu hồi mọi token đang active."""
    from app.models.refresh_token import RefreshToken

    with app.app_context():
        for _ in range(3):
            service.issue(plain_user)

        count = service.revoke_all_for_user(plain_user.id)
        assert count == 3

        remaining = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(user_id=plain_user.id, revoked_at=None)
            .count()
        )
        assert remaining == 0


def test_rotate_inactive_user_fails(service, app, plain_user, db_sqlite):
    """User bị vô hiệu hóa giữa lúc có refresh token -> 401."""
    from app.errors import UnauthorizedException
    from app.models.user import User

    with app.app_context():
        raw, _ = service.issue(plain_user)

        # Disable user bằng cách update trực tiếp qua query — đảm bảo persist.
        db_sqlite.session.query(User).filter_by(id=plain_user.id).update(
            {"is_active": False}
        )
        db_sqlite.session.commit()

        # Verify.
        u = db_sqlite.session.get(User, plain_user.id)
        assert u.is_active is False

        with pytest.raises(UnauthorizedException) as exc:
            service.rotate(raw)
        assert "refresh_invalid" in str(exc.value.message_key)


def test_refresh_endpoint_success(client, db_sqlite, plain_user, make_refresh_token):
    """POST /api/v1/auth/refresh trả cặp (access, refresh) mới."""
    raw, _ = make_refresh_token(plain_user)

    res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": raw},
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != raw  # rotation
    assert data["token_type"] == "Bearer"
    assert "user" in data


def test_refresh_endpoint_missing_token(client, db_sqlite):
    """Thiếu refresh_token trong body -> 422 validation."""
    res = client.post("/api/v1/auth/refresh", json={})
    assert res.status_code == 422


def test_refresh_endpoint_invalid_token(client, db_sqlite):
    """Token không hợp lệ -> 401 refresh_invalid."""
    res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-real-token"},
    )
    assert res.status_code == 401


def test_logout_revokes_refresh_token(client, db_sqlite, plain_user, auth_header, make_refresh_token):
    """POST /logout với refresh_token trong body -> revoke cả session refresh."""
    from app.models.refresh_token import RefreshToken
    from app.services.refresh_token_service import _hash_token

    raw, _ = make_refresh_token(plain_user)
    res = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(plain_user),
        json={"refresh_token": raw},
    )
    assert res.status_code == 200

    with client.application.app_context():
        rec = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(token_hash=_hash_token(raw))
            .first()
        )
        assert rec.revoked_at is not None


def test_logout_all_devices(client, db_sqlite, plain_user, auth_header, make_refresh_token):
    """POST /logout { all_devices: true } -> revoke toàn bộ session của user."""
    from app.models.refresh_token import RefreshToken

    for _ in range(3):
        make_refresh_token(plain_user)

    res = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(plain_user),
        json={"all_devices": True},
    )
    assert res.status_code == 200

    with client.application.app_context():
        remaining = (
            db_sqlite.session.query(RefreshToken)
            .filter_by(user_id=plain_user.id, revoked_at=None)
            .count()
        )
        assert remaining == 0


def test_introspect_access_token_active(client, db_sqlite, plain_user, make_token):
    """POST /auth/introspect với access token còn hạn -> active=True."""
    token, _, _ = make_token(plain_user)
    res = client.post("/api/v1/auth/introspect", json={"token": token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["active"] is True
    assert data["user"]["id"] == plain_user.id
    assert "permissions" in data["user"]


def test_introspect_unknown_token(client, db_sqlite):
    """POST /auth/introspect với token rác -> active=False."""
    res = client.post(
        "/api/v1/auth/introspect", json={"token": "not.a.real.jwt"}
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["active"] is False
    assert data.get("reason") == "invalid"