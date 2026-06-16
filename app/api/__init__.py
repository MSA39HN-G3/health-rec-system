def register_blueprints(app):
    from .v1.auth import bp as auth_v1_bp

    app.register_blueprint(auth_v1_bp)
