def register_blueprints(app):
    from .v1.admin import bp as admin_v1_bp
    from .v1.auth import bp as auth_v1_bp
    from .v1.departments import bp as departments_v1_bp
    from .v1.doctors import bp as doctors_v1_bp
    from .v1.symptoms import bp as symptoms_v1_bp

    app.register_blueprint(auth_v1_bp)
    app.register_blueprint(admin_v1_bp)
    app.register_blueprint(departments_v1_bp)
    app.register_blueprint(doctors_v1_bp)
    app.register_blueprint(symptoms_v1_bp)
