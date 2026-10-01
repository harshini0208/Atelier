"""Database engine: SQLite locally, Cloud SQL for PostgreSQL (via the Cloud SQL Python Connector) in the cloud."""
from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings


def _db_password() -> str:
    if os.getenv("DB_PASSWORD"):
        return os.environ["DB_PASSWORD"]
    from google.auth.transport.requests import AuthorizedSession

    from .gcp_auth import credentials

    s = get_settings()
    url = (f"https://secretmanager.googleapis.com/v1/projects/{s.project}/secrets/"
           f"{s.sql['password_secret']}/versions/latest:access")
    r = AuthorizedSession(credentials()).get(url, timeout=20)
    r.raise_for_status()
    return base64.b64decode(r.json()["payload"]["data"]).decode()


@lru_cache(maxsize=1)
def engine() -> Engine:
    s = get_settings()
    if s.db_backend == "cloudsql":
        from google.cloud.sql.connector import Connector

        from .gcp_auth import credentials

        connector = Connector(credentials=credentials())
        password = _db_password()

        def creator():  # noqa: ANN202
            return connector.connect(s.cloudsql_connection_name, "pg8000", user=s.sql["user"],
                                     password=password, db=s.sql["database"])

        return create_engine("postgresql+pg8000://", creator=creator, pool_size=5, max_overflow=2,
                             pool_pre_ping=True, pool_recycle=1800)
    s.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{s.sqlite_path}", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _pragma(conn, _):  # noqa: ANN001
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    return eng


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
