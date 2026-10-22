import sqlite3

from fastapi import APIRouter, Depends

from app.models import HealthStatus
from app.repositories.database import get_db

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
def health(conn: sqlite3.Connection = Depends(get_db)) -> HealthStatus:
    conn.execute("SELECT 1").fetchone()
    return HealthStatus(status="ok")
