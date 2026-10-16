# app/config.py
from karan_sso import SsoSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

_base_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    env_ignore_empty=True,
    extra="ignore",
)


class DatabaseSettings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_ECHO: bool = False

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "all_projects"

    GARAGE_ENDPOINT_URL: str
    GARAGE_ACCESS_KEY: str
    GARAGE_SECRET_KEY: str
    GARAGE_BUCKET_NAME: str
    GARAGE_REGION_NAME: str

    model_config = _base_config

    @property
    def POSTGRES_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


class AuthSettings(BaseSettings):
    ENVIRONMENT: str = "development"

    # SSO (shared karan_sso SDK; see karan_sso/ and the SSO contract)
    # Internal URL of the SSO API, e.g. http://sso-backend:8000/api
    SSO_BASE_URL: str = "http://localhost:8000/api"
    # Public issuer (JWT `iss`), e.g. https://auth.karanparmar.in/api/auth. Empty = don't check.
    SSO_ISSUER: str = ""
    SSO_AUDIENCE: str = "karanparmar-apps"
    # Turn on once SSO sets JWT_AUDIENCE.
    SSO_REQUIRE_AUDIENCE: bool = False
    # This app's id in SSO (app-scoped roles, e.g. {"allprojects": ["admin"]}).
    SSO_APP_ID: str = "allprojects"
    # Legacy HS256 shared secret — only while SSO still signs HS256 (rollout).
    SSO_JWT_SECRET: str = ""

    model_config = _base_config

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() == "production"

    def sso_settings(self) -> SsoSettings:
        """SDK settings built from this app's env."""
        return SsoSettings(
            SSO_BASE_URL=self.SSO_BASE_URL,
            SSO_ISSUER=self.SSO_ISSUER,
            SSO_AUDIENCE=self.SSO_AUDIENCE,
            SSO_REQUIRE_AUDIENCE=self.SSO_REQUIRE_AUDIENCE,
            SSO_JWT_SECRET=self.SSO_JWT_SECRET,
            SSO_APP_ID=self.SSO_APP_ID,
        )


_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")


class CorsSettings(BaseSettings):
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:1576,"
        "http://localhost:1577,http://localhost:4173,http://localhost:4174,"
        "https://app.karanparmar.in,https://karanparmar.in,https://www.karanparmar.in"
    )

    model_config = _base_config

    @property
    def allowed_origins(self) -> list[str]:
        """Explicit origins. Localhost origins are dropped in production."""
        origins = [
            origin.strip().rstrip("/")
            for origin in (self.CORS_ALLOWED_ORIGINS or "").split(",")
            if origin.strip() and origin.strip() != "*"
        ]
        if self.ENVIRONMENT.strip().lower() == "production":
            origins = [
                o
                for o in origins
                if not any(f"://{host}" in o for host in _LOCAL_HOSTS)
            ]
        return origins


class MediaSettings(BaseSettings):
    MEDIA_MAX_IMAGE_BYTES: int = 5_242_880
    MEDIA_MAX_DOCUMENT_BYTES: int = 10_485_760
    MEDIA_ALLOWED_IMAGE_TYPES: str = (
        "image/png,image/jpeg,image/webp,image/svg+xml,image/avif"
    )
    MEDIA_ALLOWED_DOCUMENT_TYPES: str = "application/pdf"
    MEDIA_CACHE_MAX_AGE_SECONDS: int = 31_536_000
    PUBLIC_API_URL: str = "http://localhost:8002"

    model_config = _base_config

    @property
    def allowed_image_types(self) -> set[str]:
        return {t.strip() for t in self.MEDIA_ALLOWED_IMAGE_TYPES.split(",") if t.strip()}

    @property
    def allowed_document_types(self) -> set[str]:
        return {
            t.strip() for t in self.MEDIA_ALLOWED_DOCUMENT_TYPES.split(",") if t.strip()
        }


db_settings = DatabaseSettings()  # type: ignore[call-arg]
auth_settings = AuthSettings()  # type: ignore[call-arg]
cors_settings = CorsSettings()  # type: ignore[call-arg]
media_settings = MediaSettings()  # type: ignore[call-arg]
