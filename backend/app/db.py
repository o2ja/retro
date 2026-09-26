"""Engine, session and the shared column types."""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, TypeDecorator, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

CENTS = Decimal("0.01")


class Money(TypeDecorator):
    """NUMERIC(12,2) on Postgres; TEXT on SQLite so dev money never touches a float."""

    impl = Numeric(12, 2)
    cache_ok = True

    def load_dialect_impl(self, dialect):  # noqa: ANN001, ANN201
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(24))
        return dialect.type_descriptor(Numeric(12, 2))

    def process_bind_param(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return None
        quantized = Decimal(str(value)).quantize(CENTS)
        return str(quantized) if dialect.name == "sqlite" else quantized

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN201
        return None if value is None else Decimal(str(value)).quantize(CENTS)


class UTCDateTime(TypeDecorator):
    """Always hand back timezone-aware UTC, including on SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN201
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
