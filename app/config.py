import os


class BaseConfig:

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/health_rec",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "en")
    SUPPORTED_LOCALES = ("en", "vi")

    # --- JWT (token phiên do hệ thống tự cấp sau khi đăng nhập) ---
    JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    # Thời gian sống của access token (giây). Mặc định 3600 = 1 giờ.
    JWT_EXPIRES = int(os.getenv("JWT_EXPIRES", "3600"))

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback"
    )
    GOOGLE_OAUTH_SCOPES = os.getenv("GOOGLE_OAUTH_SCOPES", "openid email profile")
    # Thời gian sống của `state` chống CSRF (giây). Quá hạn coi như không hợp lệ.
    GOOGLE_OAUTH_STATE_TTL = int(os.getenv("GOOGLE_OAUTH_STATE_TTL", "600"))

    # --- CORS ---
    # Danh sách origin của FE được phép gọi API, phân tách bằng dấu phẩy.
    # "*" cho phép mọi origin (chỉ nên dùng ở dev).
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    CORS_SUPPORTS_CREDENTIALS = (
        os.getenv("CORS_SUPPORTS_CREDENTIALS", "true").lower() == "true"
    )

    # --- Rate limit (thuật toán Token Bucket, theo IP + endpoint) ---
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    # Số token tối đa trong giỏ = số request burst tối đa cho phép tức thời.
    RATELIMIT_CAPACITY = float(os.getenv("RATELIMIT_CAPACITY", "120"))
    # Tốc độ hồi token (token/giây) = tốc độ request ổn định cho phép.
    # Mặc định 2/s ~ 120 request/phút.
    RATELIMIT_REFILL_RATE = float(os.getenv("RATELIMIT_REFILL_RATE", "2.0"))

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Bỏ qua không ghi log truy cập cho các path này (tách bằng dấu phẩy).
    LOG_SKIP_PATHS = os.getenv("LOG_SKIP_PATHS", "/health")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False  # không giới hạn khi chạy test


_CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name=None):
    name = name or os.getenv("FLASK_ENV", "development")
    return _CONFIG_MAP.get(name, DevelopmentConfig)
