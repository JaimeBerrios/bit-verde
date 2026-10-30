from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Boolean, Text, Numeric, Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.campaign import Category

def now():
    return datetime.now(timezone.utc)

class TriviaSession(Base):
    __tablename__ = "trivia_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    questions: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int | None] = mapped_column(Integer)
    token: Mapped[str | None] = mapped_column(String(40), unique=True)
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime)

class Donation(Base):
    __tablename__ = "donations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    alias: Mapped[str] = mapped_column(String(80))
    category: Mapped[Category] = mapped_column(SQLAlchemyEnum(
        Category, values_callable=lambda enum: [item.value for item in enum],
        name="donation_category", native_enum=False, create_constraint=True,
        validate_strings=True, length=50,
    ))
    quantity: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Numeric(10, 3))
    payload_hex: Mapped[str] = mapped_column(Text)
    payload_binary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Reward(Base):
    """Premios emitidos por trivia o entrega, sin datos personales del visitante."""
    __tablename__ = "rewards"
    token: Mapped[str] = mapped_column(String(40), primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DonationRequest(Base):
    """Clave de reintento guardada junto con la entrega en una sola transacción."""
    __tablename__ = "donation_requests"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    donation_id: Mapped[str] = mapped_column(String(32), unique=True)
