from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from observatory.config import get_settings
from observatory.db.models import Base


def make_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        else:
            from pathlib import Path

            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - driver hook
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def create_schema(engine: Engine) -> None:
    """Bring a database to the latest schema. In-memory SQLite (unit tests) uses the models directly; any file or
    server database goes through the Alembic migrations, so development and production share one path."""
    if engine.url.database in (None, "", ":memory:"):
        Base.metadata.create_all(engine)
        return
    migrate(str(engine.url.render_as_string(hide_password=False)))


def migrate(url: str) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from observatory.config import PROJECT_ROOT

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    tables = set(inspect(create_engine(url)).get_table_names())
    if tables and "alembic_version" not in tables:
        # databases created before migrations were wired in (via create_all) match revision 0001
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
