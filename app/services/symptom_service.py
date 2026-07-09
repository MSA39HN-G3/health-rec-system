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

    def get_recommendations(self, symptom_names):
        """Gợi ý chuyên khoa (top 3) dựa trên triệu chứng được truyền vào."""
        # 1. Lấy tất cả các khoa
        departments = self.departments.find_all()

        results = []
        for dept in departments:
            score = 0.0
            matched_keywords = []

            # Chuẩn hóa danh sách triệu chứng đầu vào
            normalized_symptoms = [s.strip().lower() for s in symptom_names]

            # Chuẩn hóa keywords và conditions của khoa
            dept_keywords = [k.strip().lower() for k in (dept.keywords or [])]
            dept_conditions = [c.strip().lower() for c in (dept.conditions or [])]

            # Thuật toán so khớp:
            for sym in normalized_symptoms:
                # 1. Khớp hoàn toàn từ khóa
                if sym in dept_keywords:
                    score += 0.4
                    matched_keywords.append(sym)
                # 2. Khớp một phần từ khóa
                elif any(sym in kw or kw in sym for kw in dept_keywords):
                    score += 0.25
                    matched_keywords.append(sym)
                # 3. Khớp hoàn toàn bệnh lý
                elif sym in dept_conditions:
                    score += 0.3
                    matched_keywords.append(sym)
                # 4. Khớp một phần bệnh lý
                elif any(sym in cond or cond in sym for cond in dept_conditions):
                    score += 0.15
                    matched_keywords.append(sym)
                # 5. Khớp mô tả khoa
                elif dept.description and sym in dept.description.lower():
                    score += 0.1
                    matched_keywords.append(sym)

            if score > 0.0:
                final_score = min(0.95, score)
                results.append((dept, final_score, matched_keywords))

        # Sắp xếp theo score giảm dần
        results.sort(key=lambda x: x[1], reverse=True)

        final_recommendations = []
        rank = 1

        # Lấy top 3 khoa khớp
        for dept, score, matched in results[:3]:
            if matched:
                explanation = f"Phát hiện triệu chứng [{', '.join(matched)}] liên quan đến các bệnh lý hoặc từ khóa chuyên môn của {dept.name}."
            else:
                explanation = f"Dựa trên triệu chứng, hệ thống nhận thấy sự tương quan với phạm vi chuyên môn của {dept.name}."

            final_recommendations.append({
                "rank": rank,
                "specialty": {
                    "id": dept.id,
                    "name": dept.name,
                    "description": dept.description
                },
                "score": round(score, 2),
                "explanation": explanation
            })
            rank += 1

        # Nếu không đủ 3, điền thêm các khoa đang hoạt động khác
        if len(final_recommendations) < 3:
            used_ids = {r["specialty"]["id"] for r in final_recommendations}
            all_active = [d for d in departments if d.id not in used_ids]
            for dept in all_active:
                if len(final_recommendations) >= 3:
                    break
                score = max(0.1, 0.4 - (rank * 0.1))
                explanation = f"Gợi ý chuyên khoa {dept.name} để hỗ trợ khám sàng lọc sức khỏe tổng quát."
                final_recommendations.append({
                    "rank": rank,
                    "specialty": {
                        "id": dept.id,
                        "name": dept.name,
                        "description": dept.description
                    },
                    "score": round(score, 2),
                    "explanation": explanation
                })
                rank += 1

        return final_recommendations

