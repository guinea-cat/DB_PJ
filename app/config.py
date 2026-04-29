from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flight Ticketing System")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite+pysqlite:///./flight_ticketing.db",
    )
    jwt_secret: str = os.getenv(
        "JWT_SECRET",
        "change-me-in-production-with-at-least-32-bytes",
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    sensitive_data_secret: str = os.getenv(
        "SENSITIVE_DATA_SECRET",
        "change-me-sensitive-secret-for-course-project",
    )
    payment_hold_minutes: int = int(os.getenv("PAYMENT_HOLD_MINUTES", "15"))
    business_timezone: str = os.getenv("BUSINESS_TIMEZONE", "Asia/Shanghai")
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    )


settings = Settings()
