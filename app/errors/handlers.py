"""Đăng ký xử lý exception tập trung cho toàn ứng dụng.

Mục tiêu: dù lỗi xảy ra ở đâu, client luôn nhận về response JSON đã chuẩn hóa
và message đúng ngôn ngữ của request.
"""
import logging

from werkzeug.exceptions import HTTPException

from ..common.response import error_response
from ..extensions import db
from ..i18n import translate
from .exceptions import AppException

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    @app.errorhandler(AppException)
    def handle_app_exception(exc):
        db.session.rollback()
        message = translate(exc.message_key, **exc.params)
        return error_response(message, exc.status_code, data=exc.details)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        db.session.rollback()
        return error_response(exc.description, exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc):
        db.session.rollback()
        logger.exception("Unhandled exception: %s", exc)
        return error_response(translate("errors.internal"), 500)
