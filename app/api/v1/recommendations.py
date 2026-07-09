"""Controller gợi ý chuyên khoa AI/Rule-based."""
import logging
from flask import Blueprint

from ...common.response import success_response
from ...errors import ValidationException
from ...extensions import db
from ...middleware import (
    Field,
    validate_body,
    validated,
)
from ...models.recommendation import Recommendation
from ...services.symptom_service import SymptomService

bp = Blueprint("recommendations", __name__, url_prefix="/api/v1/recommendations")

_symptom_service = SymptomService()
logger = logging.getLogger(__name__)


@bp.post("")
@validate_body(
    {
        "symptoms": Field(list, required=True),
    }
)
def get_recommendations():
    data = validated()
    symptoms = data["symptoms"]

    # Validate each symptom in list is a string
    if not all(isinstance(s, str) for s in symptoms):
        raise ValidationException(details={"symptoms": "must_be_list_of_strings"})

    recommendations = _symptom_service.get_recommendations(symptoms)

    # Lưu kết quả gợi ý vào database (lịch sử / thống kê gợi ý AI)
    try:
        rec_record = Recommendation(
            symptoms=symptoms,
            results=recommendations
        )
        db.session.add(rec_record)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to save recommendation to database: {e}")

    return success_response(
        {
            "recommendations": recommendations,
            "symptoms_analyzed": symptoms
        }
    )
