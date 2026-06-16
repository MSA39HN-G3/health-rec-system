"""Hỗ trợ đa ngôn ngữ (i18n) bằng JSON catalog.

- Mỗi ngôn ngữ là một file JSON trong thư mục locales/ (vi.json, en.json).
- Ngôn ngữ của request được xác định theo thứ tự ưu tiên:
      1. Query string ?lang=vi
      2. Header Accept-Language
      3. DEFAULT_LOCALE trong config
- Dùng hàm translate(key, **params) (alias `_`) để lấy chuỗi đã dịch.
  Key hỗ trợ dạng lồng nhau bằng dấu chấm, ví dụ "errors.not_found".
"""
import json
import os

from flask import g, request

_translations = {}
_default_locale = "en"
_supported_locales = ("en",)

_LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")


def init_i18n(app):
    """Nạp các file ngôn ngữ và đăng ký hook xác định locale cho mỗi request."""
    global _default_locale, _supported_locales

    _default_locale = app.config.get("DEFAULT_LOCALE", "en")
    _supported_locales = tuple(app.config.get("SUPPORTED_LOCALES", ("en",)))

    for code in _supported_locales:
        path = os.path.join(_LOCALES_DIR, f"{code}.json")
        with open(path, encoding="utf-8") as f:
            _translations[code] = json.load(f)

    @app.before_request
    def _assign_locale():
        g.locale = _resolve_locale()


def _resolve_locale():
    lang = request.args.get("lang")
    if lang and lang in _supported_locales:
        return lang
    best = request.accept_languages.best_match(_supported_locales)
    return best or _default_locale


def get_locale():
    """Lấy locale hiện tại của request (fallback về mặc định nếu ngoài request)."""
    return getattr(g, "locale", _default_locale)


def translate(key, locale=None, **params):
    """Trả về chuỗi đã dịch theo key; tự fallback về ngôn ngữ mặc định rồi về chính key."""
    locale = locale or get_locale()

    message = _lookup(_translations.get(locale, {}), key)
    if message is None and locale != _default_locale:
        message = _lookup(_translations.get(_default_locale, {}), key)
    if message is None:
        message = key  # không tìm thấy -> trả về key để dễ phát hiện thiếu chuỗi

    if params:
        try:
            message = message.format(**params)
        except (KeyError, IndexError, ValueError):
            pass
    return message


def _lookup(catalog, key):
    node = catalog
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


# Alias ngắn gọn theo quy ước phổ biến.
_ = translate
