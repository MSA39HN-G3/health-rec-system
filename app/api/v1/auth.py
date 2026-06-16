from flask import Blueprint, request

from ...common.response import success_response
from ...errors import ValidationException
from ...i18n import translate
from ...services.auth_service import AuthService

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_auth_service = AuthService()


@bp.get("/google/url")
def google_login_url():
    return success_response(_auth_service.build_google_login())


@bp.post("/google/callback")
def google_login_callback():
    data = request.get_json(silent=True) or {}
    code = (data.get("authorization_code") or "").strip()
    if not code:
        raise ValidationException(details={"required": ["authorization_code"]})

    user = _auth_service.login_with_google(code)

    return success_response(
        {"user": user.to_dict()},
        message=translate("messages.login_success"),
    )
