from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_is_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_an_unavailable_database_and_recovers_without_restart(tmp_path, monkeypatch):  # EC-34
    blocked = tmp_path / "blocked"
    blocked.mkdir()  # SQLite cannot open a directory as a database file
    monkeypatch.setenv("DOCS_DB_PATH", str(blocked))

    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {
            "code": 503,
            "title": "Database unavailable",
            "message": "The database could not be opened.",
        }
        assert str(blocked) not in response.text

        blocked.rmdir()  # SQLite can now create the file there

        assert client.get("/api/health").status_code == 200
