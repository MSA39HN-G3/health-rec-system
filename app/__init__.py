from flask import Flask

from .api import register_blueprints
from .config import get_config
from .errors import register_error_handlers
from .extensions import db, migrate
from .i18n import init_i18n
from .middleware import register_middlewares


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    app.json.sort_keys = False

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models 

    init_i18n(app)
    register_error_handlers(app)
    register_middlewares(app)
    register_blueprints(app)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app
