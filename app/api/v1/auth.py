from flask import Blueprint, g, redirect

from ...common.response import success_response
from ...i18n import translate
from ...middleware import (
    Field,
    rate_limit,
    require_auth,
    validate_body,
    validate_query,
    validated,
    validated_query,
)
from ...services.auth_service import AuthService

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_auth_service = AuthService()


@bp.get("/google/url")
@validate_query({"state": Field(str, required=True, min_length=8, max_length=128)})
def google_login_url():
    # FE tự sinh & gửi `state`; BE lưu lại rồi redirect (302) thẳng tới Google.
    state = validated_query()["state"]
    result = _auth_service.build_google_login(state)
    return redirect(result["auth_url"], code=302)


@bp.post("/google/callback")
@rate_limit(capacity=10, refill_rate=10 / 60)  # siết riêng: burst 10, ~10 req/phút
@validate_body(
    {
        "authorization_code": Field(str, required=True, min_length=1),
        "state": Field(str, required=True, min_length=8, max_length=128),
    }
)
def google_login_callback():
    data = validated()

    user, is_new = _auth_service.login_with_google(
        data["authorization_code"], data["state"]
    )

    token, expires_at = _auth_service.issue_token(user)
    message = translate("messages.onboarded" if is_new else "messages.login_success")
    return success_response(
        {
            "user": user.to_dict(),
            "is_new_user": is_new,
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat(),
        },
        message=message,
        status_code=201 if is_new else 200,  # 201 Created cho user vừa onboard
    )


@bp.get("/me")
@require_auth
def me():
    """Trả về thông tin user của token hiện tại (yêu cầu đăng nhập)."""
    return success_response({"user": g.current_user.to_dict()})


@bp.post("/logout")
@require_auth
def logout():
    """Thu hồi token hiện tại (đưa vào blacklist)."""
    _auth_service.logout(g.jwt_payload)
    return success_response(message=translate("messages.logout_success"))
