"""Unit test cho SymptomService — phủ happy path + edge case của categories + symptoms."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.errors import ConflictException, NotFoundException
from app.services.symptom_service import SymptomService


# ==========================================================================
# Categories
# ==========================================================================

def _category_repo(**overrides):
    repo = MagicMock()
    repo.find_all.return_value = overrides.pop("all", [])
    repo.find_by_id.return_value = overrides.pop("find_by_id", None)
    return repo


class TestListCategories:
    def test_returns_all_categories(self):
        c1 = MagicMock(name="c1"); c2 = MagicMock(name="c2")
        repo = _category_repo(all=[c1, c2])
        svc = SymptomService(category_repo=repo)
        assert svc.list_categories() == [c1, c2]
        repo.find_all.assert_called_once_with()


class TestGetCategory:
    def test_existing_returns_category(self):
        cat = MagicMock()
        repo = _category_repo(find_by_id=cat)
        svc = SymptomService(category_repo=repo)
        assert svc.get_category(1) is cat

    def test_missing_raises_404(self):
        repo = _category_repo(find_by_id=None)
        svc = SymptomService(category_repo=repo)
        with pytest.raises(NotFoundException):
            svc.get_category(99)


class TestCreateCategory:
    def test_persists_with_commit(self):
        repo = MagicMock()
        svc = SymptomService(category_repo=repo)
        result = svc.create_category(name="Hô hấp", description="...")
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.name == "Hô hấp"
        assert result.description == "..."


class TestUpdateCategory:
    def test_partial_update(self):
        existing = MagicMock()
        existing.name = "Old"
        existing.description = "Old desc"
        repo = MagicMock()
        repo.find_by_id.return_value = existing
        svc = SymptomService(category_repo=repo)
        result = svc.update_category(1, name="New")
        assert existing.name == "New"
        assert existing.description == "Old desc"  # giữ nguyên
        repo.commit.assert_called_once()

    def test_missing_raises(self):
        repo = MagicMock()
        repo.find_by_id.return_value = None
        svc = SymptomService(category_repo=repo)
        with pytest.raises(NotFoundException):
            svc.update_category(1, name="x")

    def test_clear_description_with_none(self):
        existing = MagicMock()
        existing.description = "Old"
        repo = MagicMock()
        repo.find_by_id.return_value = existing
        svc = SymptomService(category_repo=repo)
        svc.update_category(1, description=None)
        # code dùng `is not None` -> None không ghi đè
        assert existing.description == "Old"


class TestDeleteCategory:
    def test_delete_existing(self):
        existing = MagicMock()
        repo = MagicMock()
        repo.find_by_id.return_value = existing
        svc = SymptomService(category_repo=repo)
        svc.delete_category(5)
        repo.delete.assert_called_once_with(existing)
        repo.commit.assert_called_once()

    def test_missing_raises(self):
        repo = MagicMock()
        repo.find_by_id.return_value = None
        svc = SymptomService(category_repo=repo)
        with pytest.raises(NotFoundException):
            svc.delete_category(5)


# ==========================================================================
# Symptoms
# ==========================================================================

class TestListSymptoms:
    def test_passes_filters_to_repo(self):
        repo = MagicMock()
        repo.paginate.return_value = (["x"], 1)
        dept_repo = MagicMock()
        svc = SymptomService(symptom_repo=repo, department_repo=dept_repo)
        items, total = svc.list_symptoms(
            page=1, size=10, category_id=2, is_active=True, department_id=3
        )
        dept_repo.find_by_id.assert_called_once_with(3)
        repo.paginate.assert_called_once_with(
            1, 10, category_id=2, is_active=True, department_id=3
        )
        assert items == ["x"] and total == 1

    def test_skips_department_check_when_none(self):
        repo = MagicMock()
        repo.paginate.return_value = ([], 0)
        dept_repo = MagicMock()
        svc = SymptomService(symptom_repo=repo, department_repo=dept_repo)
        svc.list_symptoms(page=1, size=10)
        dept_repo.find_by_id.assert_not_called()

    def test_department_missing_raises_404(self):
        repo = MagicMock()
        dept_repo = MagicMock()
        dept_repo.find_by_id.return_value = None
        svc = SymptomService(symptom_repo=repo, department_repo=dept_repo)
        with pytest.raises(NotFoundException):
            svc.list_symptoms(1, 10, department_id=999)


class TestGetSymptom:
    def test_existing(self):
        s = MagicMock()
        repo = MagicMock()
        repo.find_by_id.return_value = s
        svc = SymptomService(symptom_repo=repo)
        assert svc.get_symptom(1) is s

    def test_missing_raises(self):
        repo = MagicMock()
        repo.find_by_id.return_value = None
        svc = SymptomService(symptom_repo=repo)
        with pytest.raises(NotFoundException):
            svc.get_symptom(99)


class TestCreateSymptom:
    def test_creates_with_upper_code(self):
        repo = MagicMock()
        repo.find_by_code.return_value = None
        cat_repo = MagicMock()
        cat_repo.find_by_id.return_value = MagicMock()
        svc = SymptomService(symptom_repo=repo, category_repo=cat_repo)
        result = svc.create_symptom(
            code="s-007", name="Ho khan", description="x",
            category_id=2, synonyms=["a", "b"],
        )
        repo.add.assert_called_once()
        repo.commit.assert_called_once()
        assert result.code == "S-007"
        assert result.name == "Ho khan"
        assert result.description == "x"
        assert result.category_id == 2
        assert result.synonyms == ["a", "b"]

    def test_duplicate_code_raises_conflict(self):
        repo = MagicMock()
        existing = MagicMock()
        repo.find_by_code.return_value = existing
        svc = SymptomService(symptom_repo=repo)
        with pytest.raises(ConflictException):
            svc.create_symptom(code="S-001", name="x")

    def test_invalid_category_raises(self):
        repo = MagicMock()
        repo.find_by_code.return_value = None
        cat_repo = MagicMock()
        cat_repo.find_by_id.return_value = None
        svc = SymptomService(symptom_repo=repo, category_repo=cat_repo)
        with pytest.raises(NotFoundException):
            svc.create_symptom(code="S-001", name="x", category_id=999)

    def test_synonyms_default_empty_list(self):
        repo = MagicMock()
        repo.find_by_code.return_value = None
        cat_repo = MagicMock()
        svc = SymptomService(symptom_repo=repo, category_repo=cat_repo)
        result = svc.create_symptom(code="S-001", name="x")
        assert result.synonyms == []


class TestUpdateSymptom:
    def _setup(self, existing, code_conflict=False):
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        if not code_conflict:
            srepo.find_by_code.return_value = None
        crepo = MagicMock()
        crepo.find_by_id.return_value = MagicMock()
        svc = SymptomService(symptom_repo=srepo, category_repo=crepo)
        return svc, srepo, crepo

    def test_updates_each_field(self):
        existing = MagicMock()
        existing.id = 1
        existing.code = "OLD"
        existing.category_id = None
        svc, srepo, _ = self._setup(existing)
        result = svc.update_symptom(
            1,
            code="new",
            name="New",
            description="d",
            synonyms=["s"],
            is_active=False,
        )
        assert existing.code == "NEW"
        assert existing.name == "New"
        assert existing.description == "d"
        assert existing.synonyms == ["s"]
        assert existing.is_active is False
        srepo.commit.assert_called_once()

    def test_missing_raises(self):
        srepo = MagicMock()
        srepo.find_by_id.return_value = None
        svc = SymptomService(symptom_repo=srepo)
        with pytest.raises(NotFoundException):
            svc.update_symptom(99, name="x")

    def test_code_collision_other_id_raises_conflict(self):
        existing = MagicMock()
        existing.id = 1
        existing.code = "OLD"
        other = MagicMock()
        other.id = 2  # khác 1 -> conflict
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        srepo.find_by_code.return_value = other
        svc = SymptomService(symptom_repo=srepo)
        with pytest.raises(ConflictException):
            svc.update_symptom(1, code="NEW")

    def test_code_same_id_no_conflict(self):
        existing = MagicMock()
        existing.id = 1
        existing.code = "X"
        # Same id -> hợp lệ
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        srepo.find_by_code.return_value = existing
        svc = SymptomService(symptom_repo=srepo)
        svc.update_symptom(1, code="x")
        assert existing.code == "X"

    def test_category_change_validates(self):
        existing = MagicMock()
        existing.id = 1
        existing.category_id = None
        crepo = MagicMock()
        crepo.find_by_id.return_value = None
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        svc = SymptomService(symptom_repo=srepo, category_repo=crepo)
        with pytest.raises(NotFoundException):
            svc.update_symptom(1, category_id=999)

    def test_category_set_to_none_skips_check(self):
        existing = MagicMock()
        existing.id = 1
        existing.category_id = 5
        crepo = MagicMock()
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        svc = SymptomService(symptom_repo=srepo, category_repo=crepo)
        svc.update_symptom(1, category_id=None)
        assert existing.category_id is None
        crepo.find_by_id.assert_not_called()

    def test_name_not_in_kwargs_unchanged(self):
        existing = MagicMock()
        existing.id = 1
        existing.name = "Giữ nguyên"
        srepo = MagicMock()
        srepo.find_by_id.return_value = existing
        svc = SymptomService(symptom_repo=srepo)
        svc.update_symptom(1, description="chỉ đổi desc")
        assert existing.name == "Giữ nguyên"
