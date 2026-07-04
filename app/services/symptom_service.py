from ..errors import ConflictException, NotFoundException
from ..models.symptom import Symptom
from ..models.symptom_category import SymptomCategory
from ..repositories.department_repository import DepartmentRepository
from ..repositories.symptom_category_repository import SymptomCategoryRepository
from ..repositories.symptom_repository import SymptomRepository


class SymptomService:
    def __init__(
        self,
        symptom_repo=None,
        category_repo=None,
        department_repo=None,
    ):
        self.symptoms = symptom_repo or SymptomRepository()
        self.categories = category_repo or SymptomCategoryRepository()
        self.departments = department_repo or DepartmentRepository()

    # ------------------------------------------------------------------ #
    #  Categories                                                          #
    # ------------------------------------------------------------------ #

    def list_categories(self):
        return self.categories.find_all()

    def get_category(self, category_id):
        category = self.categories.find_by_id(category_id)
        if category is None:
            raise NotFoundException("errors.symptom_category_not_found")
        return category

    def create_category(self, name, description=None):
        category = SymptomCategory(name=name, description=description)
        self.categories.add(category)
        self.categories.commit()
        return category

    def update_category(self, category_id, name=None, description=None):
        category = self.get_category(category_id)
        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        self.categories.commit()
        return category

    def delete_category(self, category_id):
        category = self.get_category(category_id)
        self.categories.delete(category)
        self.categories.commit()

    # ------------------------------------------------------------------ #
    #  Symptoms                                                            #
    # ------------------------------------------------------------------ #

    def list_symptoms(self, page, size, category_id=None, is_active=None, department_id=None):
        if department_id is not None:
            department = self.departments.find_by_id(department_id)
            if department is None:
                raise NotFoundException("errors.department_not_found")
        return self.symptoms.paginate(
            page,
            size,
            category_id=category_id,
            is_active=is_active,
            department_id=department_id,
        )

    def get_symptom(self, symptom_id):
        symptom = self.symptoms.find_by_id(symptom_id)
        if symptom is None:
            raise NotFoundException("errors.symptom_not_found")
        return symptom

    def create_symptom(self, code, name, description=None, category_id=None, synonyms=None):
        if self.symptoms.find_by_code(code) is not None:
            raise ConflictException("errors.symptom_code_exists")
        if category_id is not None:
            self.get_category(category_id)
        symptom = Symptom(
            code=code.upper(),
            name=name,
            description=description,
            category_id=category_id,
            synonyms=synonyms or [],
        )
        self.symptoms.add(symptom)
        self.symptoms.commit()
        return symptom

    def update_symptom(self, symptom_id, **kwargs):
        symptom = self.get_symptom(symptom_id)
        code = kwargs.get("code")
        if code is not None:
            code = code.upper()
            existing = self.symptoms.find_by_code(code)
            if existing is not None and existing.id != symptom_id:
                raise ConflictException("errors.symptom_code_exists")
            symptom.code = code
        if "name" in kwargs:
            symptom.name = kwargs["name"]
        if "description" in kwargs:
            symptom.description = kwargs["description"]
        if "category_id" in kwargs:
            category_id = kwargs["category_id"]
            if category_id is not None:
                self.get_category(category_id)
            symptom.category_id = category_id
        if "synonyms" in kwargs:
            symptom.synonyms = kwargs["synonyms"]
        if "is_active" in kwargs:
            symptom.is_active = kwargs["is_active"]
        self.symptoms.commit()
        return symptom
