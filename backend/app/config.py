import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "docs.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000
DEVELOPMENT = "development"


def _db_path_from_env() -> Path:
    return Path(os.environ.get("DOCS_DB_PATH", DEFAULT_DB_PATH))


def _busy_timeout_from_env() -> int:
    return int(os.environ.get("DOCS_DB_BUSY_TIMEOUT_MS", DEFAULT_BUSY_TIMEOUT_MS))


def _environment_from_env() -> str:
    return os.environ.get("DOCS_ENV", "production")


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Defaults come from the environment, so tests can pass explicit values."""

    db_path: Path = field(default_factory=_db_path_from_env)
    busy_timeout_ms: int = field(default_factory=_busy_timeout_from_env)
    environment: str = field(default_factory=_environment_from_env)

    @property
    def is_production(self) -> bool:
        # Production unless development is asked for by name, so a missing or mistyped
        # DOCS_ENV never exposes the API docs.
        return self.environment != DEVELOPMENT
