"""Unit test cho storage (Cloudflare R2 helpers)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import ServiceUnavailable

from app.errors import BadRequestException, NotFoundException
from app.services import storage


# ==========================================================================
# build_object_key
# ==========================================================================

class TestBuildObjectKey:
    def test_department_avatar_png(self):
        key = storage.build_object_key("department_avatar", "image/png")
        assert key.startswith("department/")
        assert key.endswith(".png")

    def test_image_jpeg(self):
        assert storage.build_object_key(
            "department_avatar", "image/jpeg"
        ).endswith(".jpg")

    def test_pdf(self):
        assert storage.build_object_key(
            "department_avatar", "application/pdf"
        ).endswith(".pdf")

    def test_doctor_avatar_uses_avatar_subprefix(self):
        key = storage.build_object_key("doctor_avatar", "image/png")
        assert key.startswith("doctor/avatar/")
        assert key.endswith(".png")

    def test_doctor_document_uses_document_subprefix(self):
        key = storage.build_object_key("doctor_document", "application/pdf")
        assert key.startswith("doctor/document/")
        assert key.endswith(".pdf")

    def test_unknown_kind_raises(self):
        with pytest.raises(BadRequestException):
            storage.build_object_key("unknown_kind", "image/png")

    def test_unsupported_content_type_raises(self):
        with pytest.raises(BadRequestException):
            storage.build_object_key("department_avatar", "application/zip")

    def test_each_key_is_unique(self):
        keys = {
            storage.build_object_key("department_avatar", "image/png")
            for _ in range(20)
        }
        assert len(keys) == 20


# ==========================================================================
# validate_content_type
# ==========================================================================

class TestValidateContentType:
    def test_allowed(self, app):
        # allowed mặc định: image/jpeg, image/png, image/webp, application/pdf
        storage.validate_content_type("image/png")
        storage.validate_content_type("image/jpeg")
        storage.validate_content_type("application/pdf")

    def test_disallowed_raises(self, app):
        with pytest.raises(BadRequestException):
            storage.validate_content_type("application/zip")

    def test_case_insensitive(self, app):
        storage.validate_content_type("IMAGE/PNG")


# ==========================================================================
# validate_size
# ==========================================================================

class TestValidateSize:
    def test_normal_size_ok(self, app):
        storage.validate_size(1024)

    def test_zero_raises(self, app):
        with pytest.raises(BadRequestException):
            storage.validate_size(0)

    def test_negative_raises(self, app):
        with pytest.raises(BadRequestException):
            storage.validate_size(-1)

    def test_over_max_raises(self, app):
        # default max = 15728640 (~15MB)
        with pytest.raises(BadRequestException):
            storage.validate_size(15728640 * 2)


# ==========================================================================
# is_valid_object_key
# ==========================================================================

class TestIsValidObjectKey:
    @pytest.mark.parametrize("key", [
        "department/abc.png",
        "department/abc-def-123.jpg",
        "department/abc.pdf",
        "doctor/avatar/abc.png",
        "doctor/document/abc.pdf",
    ])
    def test_valid(self, key):
        assert storage.is_valid_object_key(key) is True

    @pytest.mark.parametrize("key", [
        "",
        "x",
        "/leading-slash",
        "unknown/abc.png",   # prefix không nằm trong _KIND_PREFIXES.values()
        "doctor/abc.png",    # thiếu sub-prefix
        "doctor/wrong/abc.png",  # sub-prefix sai
        "department",        # thiếu phần tên
        "department/",       # name rỗng
        "abc\x00null.png",   # NUL
        "double//slash.png",
        "department/../../etc/passwd",
        "department/sub/abc.png",  # head="department/sub" không khớp prefix
    ])
    def test_invalid(self, key):
        assert storage.is_valid_object_key(key) is False


# ==========================================================================
# presign_put / presign_get
# ==========================================================================

class TestPresign:
    def test_presign_put_returns_url(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.generate_presigned_url.return_value = (
                "https://r2.test/bucket/key?sig=abc"
            )
            g.return_value = client
            result = storage.presign_put("department/abc.png", "image/png")
        assert result["method"] == "PUT"
        assert result["url"].startswith("https://")
        assert result["headers"]["Content-Type"] == "image/png"
        assert "expires_in" in result

    def test_presign_get_returns_url(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.generate_presigned_url.return_value = (
                "https://r2.test/bucket/key?sig=xyz"
            )
            g.return_value = client
            url = storage.presign_get("department/abc.png")
        assert url.startswith("https://")


# ==========================================================================
# head_exists
# ==========================================================================

class TestHeadExists:
    def test_returns_true_on_ok(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            g.return_value = client
            assert storage.head_exists("department/abc.png") is True
            client.head_object.assert_called_once()

    def test_no_such_key_raises_not_found(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.exceptions = MagicMock()
            client.exceptions.NoSuchKey = type("E", (Exception,), {})
            client.exceptions.NotFound = type("E", (Exception,), {})
            client.head_object.side_effect = client.exceptions.NoSuchKey("x")
            g.return_value = client
            with pytest.raises(NotFoundException):
                storage.head_exists("department/missing.png")

    def test_not_found_exception_raises_not_found(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.exceptions = MagicMock()
            client.exceptions.NoSuchKey = type("E", (Exception,), {})
            client.exceptions.NotFound = type("E", (Exception,), {})
            client.head_object.side_effect = client.exceptions.NotFound("x")
            g.return_value = client
            with pytest.raises(NotFoundException):
                storage.head_exists("department/missing.png")


# ==========================================================================
# delete_object
# ==========================================================================

class TestDeleteObject:
    def test_invalid_key_returns_false(self, app):
        assert storage.delete_object("../etc/passwd") is False

    def test_success(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.exceptions = MagicMock()
            client.exceptions.NoSuchKey = type("E", (Exception,), {})
            g.return_value = client
            assert storage.delete_object("department/abc.png") is True
            client.delete_object.assert_called_once()

    def test_key_not_found_returns_false(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.exceptions = MagicMock()
            client.exceptions.NoSuchKey = type("E", (Exception,), {})
            client.delete_object.side_effect = client.exceptions.NoSuchKey("x")
            g.return_value = client
            assert storage.delete_object("department/missing.png") is False


# ==========================================================================
# get_r2_client / _endpoint_url
# ==========================================================================

class TestGetR2Client:
    def test_missing_bucket_raises_service_unavailable(self, app):
        # Test R2_BUCKET rỗng sẽ raise ServiceUnavailable
        import os
        original = os.environ.get("R2_BUCKET")
        os.environ["R2_BUCKET"] = ""
        try:
            with app.app_context():
                # Patch current_app.config để đảm bảo R2_BUCKET rỗng
                from flask import current_app
                current_app.config["R2_BUCKET"] = ""
                current_app.config["R2_ACCESS_KEY_ID"] = ""
                with pytest.raises(ServiceUnavailable):
                    storage.get_r2_client()
        finally:
            if original is not None:
                os.environ["R2_BUCKET"] = original

    def test_missing_account_id_raises(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["R2_ACCOUNT_ID"] = ""
            with pytest.raises(ServiceUnavailable):
                storage._endpoint_url(current_app.config)


# ==========================================================================
# build_public_url / presign_get_ttl
# ==========================================================================

class TestPublicUrl:
    def test_no_host_returns_none(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["R2_PUBLIC_HOST"] = ""
            assert storage.build_public_url("department/abc.png") is None

    def test_with_host(self, app):
        from flask import current_app
        with app.app_context():
            current_app.config["R2_PUBLIC_HOST"] = "assets.example.com"
            url = storage.build_public_url("department/abc.png")
        assert "assets.example.com" in url

    def test_presigned_when_no_host(self, app):
        with patch("app.services.storage.get_r2_client") as g:
            client = MagicMock()
            client.generate_presigned_url.return_value = "https://x"
            g.return_value = client

            from flask import current_app
            with app.app_context():
                current_app.config["R2_PUBLIC_HOST"] = ""
                url = storage.presign_get("department/abc.png")
        assert url == "https://x"


def test_presign_get_ttl_returns_int(app):
    from flask import current_app
    with app.app_context():
        current_app.config["R2_PRESIGN_GET_TTL"] = 1800
        assert storage.presign_get_ttl() == 1800


# ==========================================================================
# _public_host
# ==========================================================================

def test_public_host_strips_slash(app):
    from app.services.storage import _public_host
    cfg = {"R2_PUBLIC_HOST": "https://assets.example.com/"}
    assert _public_host(cfg) == "https://assets.example.com"


def test_public_host_empty_returns_none(app):
    from app.services.storage import _public_host
    assert _public_host({"R2_PUBLIC_HOST": ""}) is None
    assert _public_host({"R2_PUBLIC_HOST": None}) is None
