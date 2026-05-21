import os
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _pem(value: str) -> str:
    """
    Convert literal \\n escape sequences (common in .env files) to real newlines.
    PEM keys require actual newline characters to be parseable by the cryptography library.
    """
    return value.replace("\\n", "\n")


class Settings:
    JWT_SECRET_KEY: str     = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str      = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    DEMO_USERNAME: str      = os.environ.get("DEMO_USERNAME", "demo")
    DEMO_PASSWORD: str      = os.environ.get("DEMO_PASSWORD", "")

    RSA_PRIVATE_KEY_PEM: str = _pem(os.environ.get("RSA_PRIVATE_KEY_PEM", ""))
    RSA_PUBLIC_KEY_PEM: str  = _pem(os.environ.get("RSA_PUBLIC_KEY_PEM", ""))

    CORS_ORIGINS: list[str] = json.loads(
        os.environ.get("CORS_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]')
    )

    GOOGLE_MAPS_API_KEY: str    = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    OUTSCRAPER_API_KEY: str     = os.environ.get("OUTSCRAPER_API_KEY", "")

    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    OSRM_BASE_URL: str      = "https://router.project-osrm.org"

    DEFAULT_LAT: float      = 24.8138   # Hsinchu City center
    DEFAULT_LON: float      = 120.9675


_settings = Settings()


def get_settings() -> Settings:
    return _settings
