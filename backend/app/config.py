"""Settings from environment variables (prefix TRACKER_) or a .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACKER_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./tracker.db"
    jwt_secret: str = DEV_SECRET
    token_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
    seed_demo: bool = False

    def check(self) -> None:
        if self.environment == "production":
            if self.jwt_secret == DEV_SECRET or len(self.jwt_secret) < 32:
                raise RuntimeError("TRACKER_JWT_SECRET must be set to a random value of 32+ characters in production")
            if self.seed_demo:
                raise RuntimeError("TRACKER_SEED_DEMO creates users with published passwords; not allowed in production")
