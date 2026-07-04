"""Unit test cho DepartmentService — phủ logic nghiệp vụ phức tạp nhất: sinh mã,
auto-grant role, đổi avatar, _cleanup_old_avatar, đụng độ mã."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.common.roles import Role
from app.errors import BadRequestException, ConflictException, NotFoundException
from app.services.department_service import DepartmentService


# ==========================================================================
# Helpers
# ==========================================================================

def _make_user_with_role(role_names=()):
    u = MagicMock()
    u.id = 42
    u.roles = []
    u.has_role = lambda *names: bool(set(role_names) & set(names))
    return u


def _svc(**kwargs):
    """Tạo service với mock repo (mặc định)."""
    dept_repo = kwargs.get("dept_repo", MagicMock())
    user_repo = kwargs.get("user_repo", MagicMock())
    role_repo = kwargs.get("role_repo", MagicMock())
    return (
        DepartmentService(
            department_repository=dept_repo,
            user_repository=user_repo,
            role_repository=role_repo,
        ),
        dept_repo,
        user_repo,
        role_repo,
    )


# ==========================================================================
# list_departments / get_stats
# ==========================================================================

class TestListDepartments:
    def test_calls_paginate(self):
        svc, d, _, _ = _svc()
        d.paginate.return_value = ([MagicMock(), MagicMock()], 2)
        items, total = svc.list_departments(page=2, size=5)
        d.paginate.assert_called_once_with(2, 5)
        assert total == 2
        assert len(items) == 2


class TestGetStats:
    def test_returns_counts(self):
        svc, d, _, _ = _svc()
        d.count_by_status.return_value = (10, 6, 4)
        result = svc.get_stats()
        assert result == {"total": 10, "active": 6, "inactive": 4}


# ==========================================================================
# create_department
# ==========================================================================

class TestCreateDepartment:
    def test_basic_create_with_auto_code(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 2
        result = svc.create_department(name="Khoa Nội")
        d.add.assert_called_once()
        d.commit.assert_called_once()
        assert result.code == "CK-003"
        assert result.name == "Khoa Nội"

    def test_no_head_inactive_is_allowed(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 0
        result = svc.create_department(name="Khoa", is_active=False)
        assert result.head_doctor_id is None
        assert result.is_active is False

    def test_active_without_head_raises_400(self):
        svc, d, u, _ = _svc()
        u.find_by_id.return_value = None
        with pytest.raises(BadRequestException):
            svc.create_department(name="Khoa", is_active=True)

    def test_head_user_not_found_raises_404(self):
        svc, d, u, _ = _svc()
        u.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.create_department(name="Khoa", head_doctor_id=99)

    def test_head_user_not_doctor_raises_400(self):
        svc, d, u, _ = _svc()
        head = _make_user_with_role(role_names=())
        u.find_by_id.return_value = head
        with pytest.raises(BadRequestException):
            svc.create_department(name="Khoa", head_doctor_id=head.id)

    def test_head_is_doctor_creates_active_department(self):
        svc, d, u, r = _svc()
        head = _make_user_with_role(role_names=[Role.DOCTOR])
        u.find_by_id.return_value = head
        d.max_code_number.return_value = 0

        dept_head_role = MagicMock()
        r.find_by_name.return_value = dept_head_role

        result = svc.create_department(
            name="Khoa", head_doctor_id=head.id, is_active=True
        )
        assert result.head_doctor_id == head.id
        # head được auto-grant role department_head
        assert dept_head_role in head.roles

    def test_code_collision_retries_and_succeeds(self):
        svc, d, _, _ = _svc()
        d.max_code_number.side_effect = [5, 6]

        # Lần commit đầu raise IntegrityError, lần 2 OK.
        d.commit.side_effect = [IntegrityError("x", {}, {}), None]

        result = svc.create_department(name="Khoa")
        assert result.code == "CK-007"  # 6+1
        assert d.rollback.call_count == 1

    def test_code_collision_exhausted_raises_conflict(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 10
        d.commit.side_effect = IntegrityError("x", {}, {})

        with pytest.raises(ConflictException):
            svc.create_department(name="Khoa")
        assert d.rollback.call_count >= 1

    def test_keywords_conditions_defaults(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 0
        result = svc.create_department(name="Khoa", keywords=None)
        assert result.keywords == []
        assert result.conditions == []
        assert result.ai_metadata == {}


# ==========================================================================
# update_department
# ==========================================================================

class TestUpdateDepartment:
    def test_not_found_raises(self):
        svc, d, _, _ = _svc()
        d.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.update_department(99, name="x")

    def test_update_name(self):
        svc, d, _, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = True
        existing.avatar_object_key = None
        existing.avatar_url = "old"
        d.find_by_id.return_value = existing

        result = svc.update_department(1, name="Mới")
        assert existing.name == "Mới"
        d.commit.assert_called_once()
        assert result is existing

    def test_change_head_invalid_user_raises_404(self):
        svc, d, u, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = False
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing
        u.find_by_id.return_value = None

        with pytest.raises(NotFoundException):
            svc.update_department(1, head_doctor_id=99)

    def test_change_head_not_doctor_raises_400(self):
        svc, d, u, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = False
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing

        head = _make_user_with_role(role_names=())
        u.find_by_id.return_value = head

        with pytest.raises(BadRequestException):
            svc.update_department(1, head_doctor_id=head.id)

    def test_set_head_makes_active(self):
        svc, d, u, r = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = False
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing

        head = _make_user_with_role(role_names=[Role.DOCTOR])
        u.find_by_id.return_value = head
        dept_head_role = MagicMock()
        r.find_by_name.return_value = dept_head_role

        svc.update_department(1, head_doctor_id=head.id)
        assert existing.head_doctor_id == head.id
        assert existing.is_active is True
        assert dept_head_role in head.roles

    def test_clear_head_makes_inactive(self):
        svc, d, u, r = _svc()
        existing = MagicMock()
        existing.head_doctor_id = 7
        existing.is_active = True
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing
        r.find_by_name.return_value = None

        svc.update_department(1, head_doctor_id=None)
        assert existing.head_doctor_id is None
        assert existing.is_active is False

    def test_update_location(self):
        svc, d, _, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = True
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing
        svc.update_department(1, location="Tầng 9")
        assert existing.location == "Tầng 9"

    def test_update_avatar_object_key_clears_cached_url(self):
        svc, d, _, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = True
        existing.avatar_object_key = "old.png"
        existing.avatar_url = "https://cached/url"
        d.find_by_id.return_value = existing

        svc.update_department(1, avatar_object_key="new.png")
        assert existing.avatar_object_key == "new.png"
        assert existing.avatar_url is None  # cache bị xoá

    def test_update_arrays_and_metadata(self):
        svc, d, _, _ = _svc()
        existing = MagicMock()
        existing.head_doctor_id = None
        existing.is_active = True
        existing.avatar_object_key = None
        existing.avatar_url = None
        d.find_by_id.return_value = existing

        svc.update_department(
            1,
            keywords=["k1", "k2"],
            conditions=["c1"],
            techniques=["t1"],
            ai_metadata={"icd10": ["A01"]},
            description="d",
            avatar_url="https://new/url",
        )
        assert existing.keywords == ["k1", "k2"]
        assert existing.conditions == ["c1"]
        assert existing.techniques == ["t1"]
        assert existing.ai_metadata == {"icd10": ["A01"]}
        assert existing.description == "d"
        assert existing.avatar_url == "https://new/url"


# ==========================================================================
# _cleanup_old_avatar (private nhưng quan trọng)
# ==========================================================================

class TestCleanupOldAvatar:
    def test_old_key_none_does_nothing(self):
        svc, *_ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar(None, "new")
            d.assert_not_called()

    def test_same_key_does_nothing(self):
        svc, *_ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar("k", "k")
            d.assert_not_called()

    def test_delete_old_key(self):
        svc, *_ = _svc()
        with patch("app.services.storage.delete_object") as d:
            svc._cleanup_old_avatar("old", "new")
            d.assert_called_once_with("old")

    def test_delete_failure_logged_not_raised(self):
        svc, *_ = _svc()
        from botocore.exceptions import BotoCoreError

        with patch(
            "app.services.storage.delete_object",
            side_effect=BotoCoreError(),
        ):
            # Không raise.
            svc._cleanup_old_avatar("old", "new")


# ==========================================================================
# _next_code
# ==========================================================================

class TestNextCode:
    def test_format_three_digits(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 8
        assert svc._next_code() == "CK-009"

    def test_format_pads_to_three(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 41
        assert svc._next_code() == "CK-042"

    def test_starts_at_001_when_empty(self):
        svc, d, _, _ = _svc()
        d.max_code_number.return_value = 0
        assert svc._next_code() == "CK-001"


# ==========================================================================
# _grant_department_head
# ==========================================================================

class TestGrantDepartmentHead:
    def test_appends_role_when_missing(self):
        svc, _, _, r = _svc()
        role = MagicMock()
        r.find_by_name.return_value = role

        user = MagicMock()
        user.roles = []
        svc._grant_department_head(user)
        assert role in user.roles

    def test_no_role_definition_is_noop(self):
        svc, _, _, r = _svc()
        r.find_by_name.return_value = None

        user = MagicMock()
        user.roles = []
        svc._grant_department_head(user)
        assert user.roles == []

    def test_already_has_role_does_not_duplicate(self):
        svc, _, _, r = _svc()
        role = MagicMock()
        r.find_by_name.return_value = role

        user = MagicMock()
        user.roles = [role]
        svc._grant_department_head(user)
        assert user.roles.count(role) == 1
