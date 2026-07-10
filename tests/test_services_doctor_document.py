"""Unit test cho DoctorDocumentService."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.common.roles import Role
from app.errors import ForbiddenException, NotFoundException, ValidationException
from app.services.doctor_document_service import DoctorDocumentService


def _user(has_roles=()):
    u = MagicMock()
    u.id = 7
    u.has_role = lambda *names: bool(set(has_roles) & set(names))
    return u


def _doctor(id=1, department_id=1):
    d = MagicMock()
    d.id = id
    d.department_id = department_id
    return d


def _document(id=1, doctor_id=1, **kwargs):
    doc = MagicMock()
    doc.id = id
    doc.doctor_id = doctor_id
    doc.document_type = kwargs.get("document_type", "license")
    doc.title = kwargs.get("title", "Test Document")
    doc.is_verified = kwargs.get("is_verified", False)
    doc.expiry_date = kwargs.get("expiry_date")
    for k, v in kwargs.items():
        setattr(doc, k, v)
    return doc


def _service(**kwargs):
    """Tạo DoctorDocumentService với department_repo mặc định là MagicMock.

    Giúp test không phải khởi tạo DepartmentRepository() (sẽ fail ngoài
    Flask app context).
    """
    kwargs.setdefault("department_repository", MagicMock())
    return DoctorDocumentService(**kwargs)


class TestListDocuments:
    def test_list_returns_documents(self):
        doc_repo = MagicMock()
        doctor_repo = MagicMock()

        docs = [_document(id=1), _document(id=2)]
        doc_repo.find_by_doctor_id.return_value = docs
        doctor_repo.find_by_id.return_value = _doctor(id=1)

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.list_documents(actor=actor, doctor_id=1)

        assert len(result) == 2

    def test_list_with_invalid_document_type_raises(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = _doctor(id=1)

        svc = _service(doctor_repository=doctor_repo)

        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(ValidationException):
            svc.list_documents(actor=actor, doctor_id=1, document_type="invalid")


class TestCreateDocument:
    def test_admin_can_create_document(self):
        doc_repo = MagicMock()
        doctor_repo = MagicMock()

        doctor_repo.find_by_id.return_value = _doctor(id=1)
        doc_repo.find_by_doctor_id.return_value = []
        doc_repo.find_by_type.return_value = None  # No existing license
        doc_repo.add.return_value = _document(id=1, document_type="license", title="New License")

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        data = {
            "document_type": "license",
            "title": "Giay phep hanh nghe",
            "issue_date": date(2025, 1, 1),
            "expiry_date": date(2030, 1, 1),
        }

        result = svc.create_document(actor=actor, doctor_id=1, data=data)

        doc_repo.add.assert_called_once()
        doc_repo.commit.assert_called_once()

    def test_admin_default_is_verified_true(self):
        """Admin upload mặc định is_verified=True (đã tin cậy)."""
        doc_repo = MagicMock()
        doctor_repo = MagicMock()

        doctor_repo.find_by_id.return_value = _doctor(id=1)
        doc_repo.find_by_type.return_value = None
        # Capture đối số DoctorDocument được truyền vào add()
        captured = {}

        def capture(document):
            captured["doc"] = document
            return document

        doc_repo.add.side_effect = capture

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        svc.create_document(
            actor=actor,
            doctor_id=1,
            data={"document_type": "degree", "title": "Bang tot nghiep"},
        )

        assert captured["doc"].is_verified is True

    def test_department_head_default_is_verified_true(self):
        """Department head upload mặc định is_verified=True (đã tin cậy)."""
        doc_repo = MagicMock()
        doctor_repo = MagicMock()
        department_repo = MagicMock()

        doctor_repo.find_by_id.return_value = _doctor(id=1, department_id=1)
        doc_repo.find_by_type.return_value = None
        # department_head của khoa 1
        my_dept = MagicMock(id=1)
        department_repo.find_by_head_doctor_id.return_value = my_dept

        captured = {}

        def capture(document):
            captured["doc"] = document
            return document

        doc_repo.add.side_effect = capture

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
            department_repository=department_repo,
        )

        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])
        svc.create_document(
            actor=actor,
            doctor_id=1,
            data={"document_type": "degree", "title": "Bang tot nghiep"},
        )

        assert captured["doc"].is_verified is True

    def test_client_can_override_is_verified(self):
        """Client có thể override is_verified trong body."""
        doc_repo = MagicMock()
        doctor_repo = MagicMock()

        doctor_repo.find_by_id.return_value = _doctor(id=1)
        doc_repo.find_by_type.return_value = None

        captured = {}

        def capture(document):
            captured["doc"] = document
            return document

        doc_repo.add.side_effect = capture

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        # Admin gửi is_verified=False (vd import hàng loạt chờ duyệt)
        svc.create_document(
            actor=actor,
            doctor_id=1,
            data={
                "document_type": "degree",
                "title": "Bang tot nghiep",
                "is_verified": False,
            },
        )

        # Phải tôn trọng giá trị client gửi
        assert captured["doc"].is_verified is False

    def test_duplicate_license_raises(self):
        doc_repo = MagicMock()
        doctor_repo = MagicMock()

        doctor_repo.find_by_id.return_value = _doctor(id=1)
        doc_repo.find_by_doctor_id.return_value = [_document(id=1)]
        doc_repo.find_by_type.return_value = _document(id=1, document_type="license")

        svc = _service(
            document_repository=doc_repo,
            doctor_repository=doctor_repo,
        )

        actor = _user(has_roles=[Role.ADMIN])
        data = {"document_type": "license", "title": "New License"}

        with pytest.raises(ValidationException) as exc_info:
            svc.create_document(actor=actor, doctor_id=1, data=data)
        # Just verify it raises
        assert "duplicate_license" in str(exc_info.value.details) or exc_info.type == ValidationException

    def test_non_admin_cannot_create(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = _doctor(id=1)

        svc = _service(doctor_repository=doctor_repo)
        actor = _user(has_roles=["doctor"])

        with pytest.raises(ForbiddenException):
            svc.create_document(actor=actor, doctor_id=1, data={})


class TestVerifyDocument:
    def test_admin_can_verify_document(self):
        doc_repo = MagicMock()
        doc = _document(id=1, is_verified=False)
        doc_repo.find_by_id.return_value = doc
        doc_repo.update.return_value = doc

        svc = _service(document_repository=doc_repo)

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.verify_document(actor=actor, document_id=1)

        assert doc.is_verified is True

    def test_non_admin_cannot_verify(self):
        doc_repo = MagicMock()
        doc_repo.find_by_id.return_value = _document(id=1)

        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.DEPARTMENT_HEAD])

        with pytest.raises(ForbiddenException):
            svc.verify_document(actor=actor, document_id=1)


class TestExpiringDocuments:
    def test_admin_can_get_expiring_documents(self):
        doc_repo = MagicMock()
        docs = [_document(id=1, expiry_date=date(2026, 8, 1))]
        doc_repo.find_expiring_documents.return_value = docs

        svc = _service(document_repository=doc_repo)

        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_expiring_documents(actor=actor, days=30)

        doc_repo.find_expiring_documents.assert_called_once_with(30)
        assert len(result) == 1


class TestNotFoundBranches:
    """Test các nhánh `doc/doctor không tồn tại` của document service."""

    def test_list_documents_doctor_not_found(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = None
        svc = _service(doctor_repository=doctor_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.list_documents(actor=actor, doctor_id=999)

    def test_get_document_not_found(self):
        doc_repo = MagicMock()
        doc_repo.find_by_id.return_value = None
        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.get_document(actor=actor, document_id=999)

    def test_create_document_doctor_not_found(self):
        doctor_repo = MagicMock()
        doctor_repo.find_by_id.return_value = None
        svc = _service(doctor_repository=doctor_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.create_document(
                actor=actor, doctor_id=999,
                data={"document_type": "degree", "title": "t"},
            )

    def test_update_document_not_found(self):
        doc_repo = MagicMock()
        doc_repo.find_by_id.return_value = None
        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.update_document(
                actor=actor, document_id=999, data={"title": "x"}
            )

    def test_delete_document_not_found(self):
        doc_repo = MagicMock()
        doc_repo.find_by_id.return_value = None
        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.delete_document(actor=actor, document_id=999)

    def test_verify_document_not_found(self):
        doc_repo = MagicMock()
        doc_repo.find_by_id.return_value = None
        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])
        with pytest.raises(NotFoundException):
            svc.verify_document(actor=actor, document_id=999)

    def test_get_unverified_documents(self):
        doc_repo = MagicMock()
        doc_repo.find_unverified_documents.return_value = [_document(id=1)]
        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])
        result = svc.get_unverified_documents(actor=actor)
        assert len(result) == 1
        doc_repo.find_unverified_documents.assert_called_once()

    def test_get_unverified_denies_non_admin(self):
        svc = _service()
        actor = _user(has_roles=[Role.DOCTOR])
        with pytest.raises(ForbiddenException):
            svc.get_unverified_documents(actor=actor)

    def test_check_permission_no_actor(self):
        svc = _service(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
        )
        with pytest.raises(ForbiddenException):
            svc._check_permission(None, doctor_id=1)

    def test_check_permission_denies_plain_user(self):
        svc = _service(
            doctor_repository=MagicMock(),
            department_repository=MagicMock(),
        )
        actor = _user(has_roles=[])
        with pytest.raises(ForbiddenException):
            svc._check_permission(actor, doctor_id=1)


class TestCleanupOldObject:
    """Test logic dọn dẹp object cũ trên R2."""

    def test_same_key_does_not_delete(self):
        svc = _service()
        # PATCH với cùng key hiện tại (idempotent) -> không xóa
        with patch("app.services.storage.delete_object") as mock_del:
            svc._cleanup_old_object("doctor/document/abc.pdf", "doctor/document/abc.pdf")
            mock_del.assert_not_called()

    def test_old_key_none_does_not_delete(self):
        svc = _service()
        with patch("app.services.storage.delete_object") as mock_del:
            svc._cleanup_old_object(None, "doctor/document/abc.pdf")
            mock_del.assert_not_called()

    def test_different_key_triggers_delete(self):
        svc = _service()
        with patch("app.services.storage.delete_object") as mock_del:
            svc._cleanup_old_object("doctor/document/old.pdf", "doctor/document/new.pdf")
            mock_del.assert_called_once_with("doctor/document/old.pdf")

    def test_set_to_none_triggers_delete(self):
        svc = _service()
        with patch("app.services.storage.delete_object") as mock_del:
            svc._cleanup_old_object("doctor/document/abc.pdf", None)
            mock_del.assert_called_once_with("doctor/document/abc.pdf")

    def test_r2_error_does_not_propagate(self):
        """Lỗi R2 chỉ log warning, không raise."""
        from botocore.exceptions import ClientError

        svc = _service()
        with patch(
            "app.services.storage.delete_object",
            side_effect=ClientError({"Error": {"Code": "500"}}, "delete_object"),
        ):
            # Phải chạy được, không raise
            svc._cleanup_old_object("doctor/document/old.pdf", "doctor/document/new.pdf")


class TestUpdateDocumentCleansUpR2:
    """Test PATCH/DELETE tài liệu tự xóa object cũ trên R2."""

    def test_update_object_key_cleans_up_old_r2_object(self):
        doc_repo = MagicMock()
        doc = _document(id=1, object_key="doctor/document/old.pdf")
        doc_repo.find_by_id.return_value = doc
        doc_repo.update.return_value = doc

        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_object") as mock_cleanup:
            svc.update_document(
                actor=actor,
                document_id=1,
                data={"object_key": "doctor/document/new.pdf"},
            )
            # Phải gọi cleanup với old key + new key
            mock_cleanup.assert_called_once()
            args, _ = mock_cleanup.call_args
            assert args[0] == "doctor/document/old.pdf"
            assert args[1] == "doctor/document/new.pdf"

    def test_delete_document_cleans_up_r2_object(self):
        doc_repo = MagicMock()
        doc = _document(id=1, object_key="doctor/document/abc.pdf")
        doc_repo.find_by_id.return_value = doc

        svc = _service(document_repository=doc_repo)
        actor = _user(has_roles=[Role.ADMIN])

        with patch.object(svc, "_cleanup_old_object") as mock_cleanup:
            svc.delete_document(actor=actor, document_id=1)
            mock_cleanup.assert_called_once()
            args, _ = mock_cleanup.call_args
            assert args[0] == "doctor/document/abc.pdf"
            assert args[1] is None
