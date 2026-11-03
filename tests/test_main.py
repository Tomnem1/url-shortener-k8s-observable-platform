import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_connection


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_urls(client):
    with get_connection() as conn:
        conn.execute("TRUNCATE urls")


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ignores_database(client, monkeypatch):
    def broken_connection():
        raise psycopg.OperationalError("database is down")

    monkeypatch.setattr("app.main.get_connection", broken_connection)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_database_unreachable(client, monkeypatch):
    def broken_connection():
        raise psycopg.OperationalError("database is down")

    monkeypatch.setattr("app.main.get_connection", broken_connection)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}


def test_shorten_creates_link(client):
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 200
    short_url = response.json()["short_url"]
    code = short_url.rsplit("/", 1)[-1]
    assert len(code) == 6
    with get_connection() as conn:
        row = conn.execute("SELECT url FROM urls WHERE code = %s", (code,)).fetchone()
    assert row == ("https://example.com",)


def test_shorten_wrong_input(client):
    response = client.post("/shorten", json={"link": "https://example.com"})
    assert response.status_code == 422
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
    assert count == 0


def test_redirect_known_code(client):
    create_response = client.post("/shorten", json={"url": "https://example.com"})
    short_url = create_response.json()["short_url"]
    code = short_url.rsplit("/", 1)[-1]

    redirect_response = client.get(f"/{code}", follow_redirects=False)

    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://example.com"


def test_redirect_unknown_code(client):
    response = client.get("/abc123")
    assert response.status_code == 404
    assert response.json() == {"detail": "Code not found"}


def test_redirect_reads_from_database(client):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO urls (code, url) VALUES (%s, %s)",
            ("dbonly", "https://example.org"),
        )

    response = client.get("/dbonly", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://example.org"
