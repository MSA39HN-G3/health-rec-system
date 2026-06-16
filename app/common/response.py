
from flask import jsonify


def success_response(data=None, message=None, status_code=200, meta=None):
    body = {"success": True, "data": data}
    if message is not None:
        body["message"] = message
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status_code


def error_response(message, status_code=400, details=None):
    error = {"code": status_code, "message": message}
    if details is not None:
        error["details"] = details
    return jsonify({"success": False, "error": error}), status_code
