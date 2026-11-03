import os
import secrets
import string
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    url TEXT NOT NULL
)
"""


def get_connection() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
    yield


app = FastAPI(lifespan=lifespan)

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 6


def generate_code() -> str:
    characters = []
    for _ in range(CODE_LENGTH):
        characters.append(secrets.choice(ALPHABET))
    code = "".join(characters)
    return code


class ShortenRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"},
        )
    return {"status": "ok"}


@app.post("/shorten")
def shorten(body: ShortenRequest, request: Request):
    with get_connection() as conn:
        code = generate_code()
        while conn.execute("SELECT 1 FROM urls WHERE code = %s", (code,)).fetchone():
            code = generate_code()
        conn.execute("INSERT INTO urls (code, url) VALUES (%s, %s)", (code, body.url))
    return {"short_url": f"{request.base_url}{code}"}


@app.get("/{code}")
def redirect(code: str):
    with get_connection() as conn:
        row = conn.execute("SELECT url FROM urls WHERE code = %s", (code,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Code not found")
    url = row[0]
    return RedirectResponse(url, status_code=307)
