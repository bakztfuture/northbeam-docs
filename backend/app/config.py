import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "docs.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000


def _db_path_from_env() -> Path:
    return Path(os.environ.get("DOCS_DB_PATH", DEFAULT_DB_PATH))


def _busy_timeout_from_env() -> int:
    return int(os.environ.get("DOCS_DB_BUSY_TIMEOUT_MS", DEFAULT_BUSY_TIMEOUT_MS))


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Defaults come from the environment, so tests can pass explicit values."""

    db_path: Path = field(default_factory=_db_path_from_env)
    busy_timeout_ms: int = field(default_factory=_busy_timeout_from_env)
