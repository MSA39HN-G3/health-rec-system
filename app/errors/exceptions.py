

class AppException(Exception):
    status_code = 400
    message_key = "errors.bad_request"

    def __init__(self, message_key=None, status_code=None, details=None, **params):
        super().__init__(message_key or self.message_key)
        if message_key is not None:
            self.message_key = message_key
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        self.params = params


class BadRequestException(AppException):
    status_code = 400
    message_key = "errors.bad_request"


class ValidationException(AppException):
    status_code = 422
    message_key = "errors.validation"


class UnauthorizedException(AppException):
    status_code = 401
    message_key = "errors.unauthorized"


class ForbiddenException(AppException):
    status_code = 403
    message_key = "errors.forbidden"


class NotFoundException(AppException):
    status_code = 404
    message_key = "errors.not_found"


class ConflictException(AppException):
    status_code = 409
    message_key = "errors.conflict"
