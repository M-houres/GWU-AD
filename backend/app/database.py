from contextlib import contextmanager
import logging
import time
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.database")


def _build_sqlite_engine():
    sqlite_engine = create_engine(
        settings.sqlite_dsn,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )

    @event.listens_for(sqlite_engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    return sqlite_engine


def _create_engine():
    mysql_engine = create_engine(
        settings.mysql_dsn,
        connect_args={
            "connect_timeout": max(int(settings.db_connect_timeout_seconds or 0), 1),
            "read_timeout": max(int(settings.db_read_timeout_seconds or 0), 1),
            "write_timeout": max(int(settings.db_write_timeout_seconds or 0), 1),
        },
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_use_lifo=True,
        future=True,
    )

    @event.listens_for(mysql_engine, "connect")
    def _configure_mysql_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            statement_timeout_ms = max(int(settings.db_statement_timeout_ms or 0), 0)
            if statement_timeout_ms > 0:
                cursor.execute(f"SET SESSION max_execution_time = {statement_timeout_ms}")
        except Exception:
            logger.warning("mysql_session_config_failed", exc_info=True)
        finally:
            cursor.close()

    attempts = max(int(settings.db_startup_retry_attempts or 0), 1)
    retry_delay = max(float(settings.db_startup_retry_delay_seconds or 0), 0.2)
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            with mysql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return mysql_engine
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            logger.warning(
                "mysql_connect_retrying",
                extra={"attempt": attempt, "max_attempts": attempts, "delay_seconds": retry_delay},
                exc_info=True,
            )
            time.sleep(retry_delay)

    if settings.is_prod:
        raise RuntimeError("生产环境数据库必须连接 MySQL，禁止回退到 SQLite") from last_exc
    if not settings.db_fallback_sqlite:
        raise last_exc if last_exc is not None else RuntimeError("mysql unavailable")
    logger.warning("mysql_unavailable_fallback_to_sqlite", extra={"app_env": settings.app_env}, exc_info=True)
    return _build_sqlite_engine()


engine = _create_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


class Base(DeclarativeBase):
    pass


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
