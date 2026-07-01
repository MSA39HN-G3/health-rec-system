from flask import Blueprint

from ...common.response import paginated_response, success_response
from ...common.roles import Permission
from ...i18n import translate
from ...middleware import (
    Field,
    require_permission,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.symptom_service import SymptomService

bp = Blueprint("symptoms", __name__, url_prefix="/api/v1/symptoms")

_symptom_service = SymptomService()


# ==========================================================================
# Categories
# ==========================================================================

@bp.get("/categories")
def list_categories():
    categories = _symptom_service.list_categories()
    return success_response([c.to_dict() for c in categories])


@bp.post("/categories")
@require_permission(Permission.SYMPTOM_MANAGE)
@validate_body(
    {
        "name": Field(str, required=True, min_length=1, max_length=255),
        "description": Field(str, required=False, max_length=1000),
    }
)
def create_category():
    data = validated()
    category = _symptom_service.create_category(
        name=data["name"],
        description=data.get("description"),
    )
    return success_response(
        category.to_dict(),
        message=translate("messages.symptom_category_created"),
        status_code=201,
    )


@bp.get("/categories/<int:category_id>")
def get_category(category_id):
    category = _symptom_service.get_category(category_id)
    return success_response(category.to_dict())


@bp.patch("/categories/<int:category_id>")
@require_permission(Permission.SYMPTOM_MANAGE)
@validate_body(
    {
        "name": Field(str, required=False, min_length=1, max_length=255),
        "description": Field(str, required=False, max_length=1000),
    }
)
def update_category(category_id):
    data = validated()
    category = _symptom_service.update_category(
        category_id,
        name=data.get("name"),
        description=data.get("description"),
    )
    return success_response(
        category.to_dict(),
        message=translate("messages.symptom_category_updated"),
    )


@bp.delete("/categories/<int:category_id>")
@require_permission(Permission.SYMPTOM_MANAGE)
def delete_category(category_id):
    _symptom_service.delete_category(category_id)
    return success_response(message=translate("messages.symptom_category_deleted"))


# ==========================================================================
# Symptoms
# ==========================================================================

@bp.get("")
@validate_query(
    {
        "page": Field(int, required=False, default=1, minimum=1),
        "size": Field(int, required=False, default=20, minimum=1, maximum=100),
        "category_id": Field(int, required=False),
        "is_active": Field(bool, required=False),
    }
)
def list_symptoms():
    q = validated_query()
    items, total = _symptom_service.list_symptoms(
        page=q["page"],
        size=q["size"],
        category_id=q.get("category_id"),
        is_active=q.get("is_active"),
    )
    return paginated_response(
        [s.to_dict() for s in items],
        page=q["page"],
        size=q["size"],
        total=total,
    )


@bp.post("")
@require_permission(Permission.SYMPTOM_MANAGE)
@validate_body(
    {
        "code": Field(str, required=True, min_length=1, max_length=50),
        "name": Field(str, required=True, min_length=1, max_length=255),
        "description": Field(str, required=False, max_length=2000),
        "category_id": Field(int, required=False),
        "synonyms": Field(list, required=False),
    }
)
def create_symptom():
    data = validated()
    symptom = _symptom_service.create_symptom(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        category_id=data.get("category_id"),
        synonyms=data.get("synonyms"),
    )
    return success_response(
        symptom.to_dict(),
        message=translate("messages.symptom_created"),
        status_code=201,
    )


@bp.get("/<int:symptom_id>")
def get_symptom(symptom_id):
    symptom = _symptom_service.get_symptom(symptom_id)
    return success_response(symptom.to_dict())


@bp.patch("/<int:symptom_id>")
@require_permission(Permission.SYMPTOM_MANAGE)
@validate_body(
    {
        "code": Field(str, required=False, min_length=1, max_length=50),
        "name": Field(str, required=False, min_length=1, max_length=255),
        "description": Field(str, required=False, max_length=2000),
        "category_id": Field(int, required=False),
        "synonyms": Field(list, required=False),
        "is_active": Field(bool, required=False),
    }
)
def update_symptom(symptom_id):
    data = validated()
    symptom = _symptom_service.update_symptom(symptom_id, **data)
    return success_response(
        symptom.to_dict(),
        message=translate("messages.symptom_updated"),
    )


@bp.delete("/<int:symptom_id>")
@require_permission(Permission.SYMPTOM_MANAGE)
def deactivate_symptom(symptom_id):
    symptom = _symptom_service.update_symptom(symptom_id, is_active=False)
    return success_response(
        symptom.to_dict(),
        message=translate("messages.symptom_deactivated"),
    )
