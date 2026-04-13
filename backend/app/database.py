from contextlib import contextmanager
import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.database")


def _create_engine():
    mysql_engine = create_engine(
        settings.mysql_dsn,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        future=True,
    )
    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return mysql_engine
    except Exception:
        if settings.is_prod:
            raise RuntimeError("生产环境数据库必须连接 MySQL，禁止回退到 SQLite")
        if not settings.db_fallback_sqlite:
            raise
        logger.warning("mysql_unavailable_fallback_to_sqlite", extra={"app_env": settings.app_env})
        return create_engine(
            settings.sqlite_dsn,
            connect_args={"check_same_thread": False},
            future=True,
        )


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
