from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session

from db import get_session
from settings import settings

app = FastAPI(title="Tally API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.frontend_origin == "*" else [settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/db-health")
def db_health(session: Session = Depends(get_session)) -> dict[str, object]:
    row = session.execute(text("SELECT 1 AS ok, current_database() AS db")).first()
    if row is None:
        return {"status": "error", "reason": "no row"}
    return {"status": "ok", "scalar": row[0], "database": row[1]}
