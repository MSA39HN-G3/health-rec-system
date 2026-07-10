"""Unit test cho RoleService và UserService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.errors import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.services.role_service import RoleService
from app.services.user_service import UserService


# ==========================================================================
# RoleService
# ==========================================================================

class TestListRoles:
    def test_returns_all(self):
        rr = MagicMock(); rr.all.return_value = ["r1", "r2"]
        svc = RoleService(role_repository=rr)
        assert svc.list_roles() == ["r1", "r2"]


class TestListPermissions:
    def test_returns_all(self):
        pr = MagicMock(); pr.all.return_value = ["p1"]
        svc = RoleService(permission_repository=pr)
        assert svc.list_permissions() == ["p1"]


class TestCreateRole:
    def test_creates_and_commits(self):
        rr = MagicMock()
        rr.find_by_name.return_value = None
        svc = RoleService(role_repository=rr)
        role = svc.create_role(name="admin", description="...")
        rr.add.assert_called_once()
        rr.commit.assert_called_once()
        assert role.name == "admin"

    def test_duplicate_name_raises_conflict(self):
        rr = MagicMock()
        rr.find_by_name.return_value = MagicMock()
        svc = RoleService(role_repository=rr)
        with pytest.raises(ConflictException):
            svc.create_role(name="admin")


class TestAddPermission:
    def test_role_not_found(self):
        rr = MagicMock(); rr.find_by_id.return_value = None
        pr = MagicMock()
        svc = RoleService(role_repository=rr, permission_repository=pr)
        with pytest.raises(NotFoundException):
            svc.add_permission(1, "x:y")

    def test_permission_not_found(self):
        rr = MagicMock(); rr.find_by_id.return_value = MagicMock()
        pr = MagicMock(); pr.find_by_name.return_value = None
        svc = RoleService(role_repository=rr, permission_repository=pr)
        with pytest.raises(NotFoundException):
            svc.add_permission(1, "x:y")

    def test_adds_permission(self):
        role = MagicMock(); role.permissions = []
        rr = MagicMock(); rr.find_by_id.return_value = role
        perm = MagicMock()
        pr = MagicMock(); pr.find_by_name.return_value = perm
        svc = RoleService(role_repository=rr, permission_repository=pr)
        svc.add_permission(1, "x:y")
        assert perm in role.permissions
        rr.commit.assert_called_once()

    def test_idempotent_when_already(self):
        role = MagicMock(); perm = MagicMock(); role.permissions = [perm]
        rr = MagicMock(); rr.find_by_id.return_value = role
        pr = MagicMock(); pr.find_by_name.return_value = perm
        svc = RoleService(role_repository=rr, permission_repository=pr)
        svc.add_permission(1, "x:y")
        rr.commit.assert_not_called()


class TestRemovePermission:
    def test_role_not_found(self):
        rr = MagicMock(); rr.find_by_id.return_value = None
        pr = MagicMock()
        svc = RoleService(role_repository=rr, permission_repository=pr)
        with pytest.raises(NotFoundException):
            svc.remove_permission(1, "x:y")

    def test_permission_missing_is_noop(self):
        role = MagicMock(); role.permissions = []
        rr = MagicMock(); rr.find_by_id.return_value = role
        pr = MagicMock(); pr.find_by_name.return_value = None
        svc = RoleService(role_repository=rr, permission_repository=pr)
        svc.remove_permission(1, "x:y")
        rr.commit.assert_not_called()

    def test_removes_existing(self):
        role = MagicMock(); perm = MagicMock(); role.permissions = [perm]
        rr = MagicMock(); rr.find_by_id.return_value = role
        pr = MagicMock(); pr.find_by_name.return_value = perm
        svc = RoleService(role_repository=rr, permission_repository=pr)
        svc.remove_permission(1, "x:y")
        assert perm not in role.permissions
        rr.commit.assert_called_once()


# ==========================================================================
# UserService
# ==========================================================================

def _make_user_service(**kw):
    ur = kw.get("user_repo", MagicMock())
    rr = kw.get("role_repo", MagicMock())
    return (
        UserService(user_repository=ur, role_repository=rr),
        ur,
        rr,
    )


class TestListUsers:
    def test_passes_pagination(self):
        svc, ur, _ = _make_user_service()
        ur.paginate.return_value = (["u1", "u2"], 2)
        items, total = svc.list_users(page=1, size=10)
        ur.paginate.assert_called_once_with(1, 10)
        assert total == 2


class TestGetUser:
    def test_existing(self):
        svc, ur, _ = _make_user_service()
        ur.find_by_id.return_value = MagicMock()
        assert svc.get_user(1) is not None

    def test_missing_raises(self):
        svc, ur, _ = _make_user_service()
        ur.find_by_id.return_value = None
        with pytest.raises(NotFoundException):
            svc.get_user(99)


class TestAddRole:
    def test_role_missing_raises(self):
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = MagicMock()
        rr.find_by_name.return_value = None
        with pytest.raises(NotFoundException):
            svc.add_role(1, "x")

    def test_user_missing_raises(self):
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = None
        rr.find_by_name.return_value = MagicMock()
        with pytest.raises(NotFoundException):
            svc.add_role(1, "x")

    def test_adds_role(self):
        user = MagicMock(); user.roles = []
        role = MagicMock()
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = user
        rr.find_by_name.return_value = role
        svc.add_role(1, "x")
        assert role in user.roles
        ur.commit.assert_called_once()

    def test_idempotent(self):
        user = MagicMock(); role = MagicMock(); user.roles = [role]
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = user
        rr.find_by_name.return_value = role
        svc.add_role(1, "x")
        ur.commit.assert_not_called()


class TestSetActive:
    def test_disable_other_user(self):
        user = MagicMock(); user.id = 5
        svc, ur, _ = _make_user_service()
        ur.find_by_id.return_value = user
        svc.set_active(5, is_active=False, acting_user_id=99)
        assert user.is_active is False
        ur.commit.assert_called_once()

    def test_cannot_disable_self(self):
        user = MagicMock(); user.id = 5
        svc, ur, _ = _make_user_service()
        ur.find_by_id.return_value = user
        with pytest.raises(BadRequestException):
            svc.set_active(5, is_active=False, acting_user_id=5)

    def test_acting_user_none_allows(self):
        user = MagicMock(); user.id = 5
        svc, ur, _ = _make_user_service()
        ur.find_by_id.return_value = user
        svc.set_active(5, is_active=False, acting_user_id=None)
        assert user.is_active is False


class TestRemoveRole:
    def test_user_missing_raises(self):
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = None
        rr.find_by_name.return_value = MagicMock()
        with pytest.raises(NotFoundException):
            svc.remove_role(1, "x")

    def test_role_missing_is_noop(self):
        user = MagicMock(); user.roles = []
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = user
        rr.find_by_name.return_value = None
        svc.remove_role(1, "x")
        ur.commit.assert_not_called()

    def test_removes_role(self):
        user = MagicMock(); role = MagicMock(); user.roles = [role]
        svc, ur, rr = _make_user_service()
        ur.find_by_id.return_value = user
        rr.find_by_name.return_value = role
        svc.remove_role(1, "x")
        assert role not in user.roles
        ur.commit.assert_called_once()


class TestSearchUsers:
    def test_calls_repo_search(self):
        svc, ur, _ = _make_user_service()
        ur.search.return_value = (["u1"], 1)
        items, total = svc.search_users("nguyen", page=1, size=10)
        ur.search.assert_called_once_with("nguyen", 1, 10)
        assert total == 1

    def test_repo_returns_empty(self):
        svc, ur, _ = _make_user_service()
        ur.search.return_value = ([], 0)
        items, total = svc.search_users("xyz", page=1, size=10)
        assert total == 0
        assert items == []


class TestFilterUsers:
    def test_filter_by_role(self):
        svc, ur, _ = _make_user_service()
        ur.filter.return_value = (["u1"], 1)
        items, total = svc.filter_users(page=1, size=10, role="admin")
        ur.filter.assert_called_once_with(1, 10, role="admin", is_active=None)
        assert total == 1

    def test_filter_by_is_active(self):
        svc, ur, _ = _make_user_service()
        ur.filter.return_value = (["u1", "u2"], 2)
        items, total = svc.filter_users(page=1, size=10, is_active=True)
        ur.filter.assert_called_once_with(1, 10, role=None, is_active=True)
        assert total == 2

    def test_filter_combined(self):
        svc, ur, _ = _make_user_service()
        ur.filter.return_value = ([], 0)
        items, total = svc.filter_users(page=2, size=5, role="doctor", is_active=False)
        ur.filter.assert_called_once_with(2, 5, role="doctor", is_active=False)

    def test_filter_no_params(self):
        svc, ur, _ = _make_user_service()
        ur.filter.return_value = (["u1"], 1)
        items, total = svc.filter_users(page=1, size=20)
        ur.filter.assert_called_once_with(1, 20, role=None, is_active=None)
