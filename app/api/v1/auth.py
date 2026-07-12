from flask import Blueprint, g, redirect, request

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


def _client_ip():
    """Lấy IP client từ request — dùng cho audit log refresh token.

    Ưu tiên ``X-Forwarded-For`` (reverse proxy) trước, fallback ``request.remote_addr``.
    """
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        # Header có thể chứa nhiều IP phân tách bằng dấu phẩy — lấy IP đầu tiên.
        return fwd.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def _client_user_agent():
    return (request.headers.get("User-Agent", "") or "")[:512]


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

    tokens = _auth_service.issue_token(
        user,
        created_ip=_client_ip(),
        user_agent=_client_user_agent(),
    )
    message = translate("messages.onboarded" if is_new else "messages.login_success")
    return success_response(
        {
            "user": user.to_dict(),
            "is_new_user": is_new,
            "access_token": tokens["access_token"],
            "token_type": "Bearer",
            "expires_at": tokens["access_expires_at"].isoformat(),
            "refresh_token": tokens["refresh_token"],
            "refresh_expires_at": tokens["refresh_expires_at"].isoformat(),
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
@validate_body(
    {
        # Optional: FE gửi kèm refresh_token để thu hồi cả session refresh.
        # Nếu không gửi, BE chỉ blacklist access token hiện tại.
        "refresh_token": Field(str, required=False, min_length=1, max_length=512),
        # Optional: ``all_devices=true`` để logout khỏi mọi thiết bị (revoke all refresh).
        "all_devices": Field(bool, required=False, default=False),
    }
)
def logout():
    """Thu hồi token hiện tại (đưa access vào blacklist + revoke refresh)."""
    data = validated()
    _auth_service.logout(g.jwt_payload)

    user = g.current_user
    payload_data = data or {}
    refresh_raw = payload_data.get("refresh_token")
    revoke_all = payload_data.get("all_devices", False)

    if revoke_all:
        _auth_service.revoke_all_refresh_tokens(user.id)
    elif refresh_raw:
        _auth_service.revoke_refresh_token(refresh_raw)

    return success_response(message=translate("messages.logout_success"))


@bp.post("/refresh")
@rate_limit(capacity=30, refill_rate=0.5)  # chống brute force: ~30 req/phút
@validate_body({"refresh_token": Field(str, required=True, min_length=1, max_length=512)})
def refresh_token():
    """Đổi refresh token lấy cặp (access mới, refresh mới — xoay vòng).

    Body: ``{ "refresh_token": "<opaque>" }``.

    Response 200: ``{ access_token, expires_at, refresh_token, refresh_expires_at, user }``.

    Response 401:
      - ``errors.refresh_invalid``: token không tồn tại / hết hạn / bị thu hồi.
      - ``errors.refresh_reuse_detected``: token đã bị thu hồi nhưng giờ lại được
        dùng -> coi như bị lộ, mọi session của user đã bị logout. FE buộc phải
        login lại qua Google.

    Idempotent: gọi lại với cùng refresh_token trong khoảng < 1s có thể
    dẫn tới reuse-detection (token đã revoke ở request trước). Đây là behavior
    đúng của rotation — FE chỉ nên gọi /refresh 1 lần / song song.
    """
    data = validated()
    result = _auth_service.refresh(
        data["refresh_token"],
        created_ip=_client_ip(),
        user_agent=_client_user_agent(),
    )
    return success_response(
        {
            "user": result["user"].to_dict(),
            "access_token": result["access_token"],
            "token_type": "Bearer",
            "expires_at": result["access_expires_at"].isoformat(),
            "refresh_token": result["refresh_token"],
            "refresh_expires_at": result["refresh_expires_at"].isoformat(),
        }
    )


@bp.post("/introspect")
@validate_body({"token": Field(str, required=True, min_length=1)})
def introspect_token():
    """Kiểm tra trạng thái một token (theo RFC 7662).

    Trả về `{ "data": { "active": bool, ... } }`:
      - active=false: token không hợp lệ / hết hạn / đã bị thu hồi /
        user không còn tồn tại (kèm `reason` để dễ debug).
      - active=true: kèm `sub`, `jti`, `exp`, `expires_in` (giây còn lại),
        và `user` (id, email, roles, permissions, is_active).

    Đây là API public (không cần đăng nhập) vì nó chỉ kiểm tra token:
    endpoint này được thiết kế để gateway/reverse proxy / FE gọi trước
    khi thực hiện request đến resource server — tương tự OAuth 2.0
    Token Introspection Endpoint.

    Lưu ý: khi gọi với chính token của request hiện tại, BE sẽ đi qua
    validate_token đầy đủ (decode + blacklist + user còn active) nên
    endpoint này cũng có thể được dùng để tự kiểm tra token của mình.
    """
    data = validated()
    result = _auth_service.introspect_token(data["token"])
    return success_response(result)
