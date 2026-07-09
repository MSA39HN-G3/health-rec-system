def register_blueprints(app):
    from .v1.admin import bp as admin_v1_bp
    from .v1.auth import bp as auth_v1_bp
    from .v1.departments import bp as departments_v1_bp
    from .v1.doctors import bp as doctors_v1_bp
    from .v1.doctor_documents import bp as doctor_documents_v1_bp
    from .v1.doctor_statistics import bp as doctor_statistics_v1_bp
    from .v1.doctor_ratings import bp as doctor_ratings_v1_bp
    from .v1.symptoms import bp as symptoms_v1_bp
    from .v1.uploads import bp as uploads_v1_bp
    from .v1.patients import bp as patients_v1_bp
    from .v1.recommendations import bp as recommendations_v1_bp
    from .v1.booking_sessions import bp as booking_sessions_v1_bp

    app.register_blueprint(auth_v1_bp)
    app.register_blueprint(admin_v1_bp)
    app.register_blueprint(departments_v1_bp)
    app.register_blueprint(doctors_v1_bp)
    app.register_blueprint(doctor_documents_v1_bp)
    app.register_blueprint(doctor_statistics_v1_bp)
    app.register_blueprint(doctor_ratings_v1_bp)
    app.register_blueprint(symptoms_v1_bp)
    app.register_blueprint(uploads_v1_bp)
    app.register_blueprint(patients_v1_bp)
    app.register_blueprint(recommendations_v1_bp)
    app.register_blueprint(booking_sessions_v1_bp)

