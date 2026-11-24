"""SQLAlchemy models for Bitrix Randomizer."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Portal(Base):
    """Connected Bitrix24 portal."""

    __tablename__ = "portals"

    # Internal portal identifier.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Portal domain, for example: company.bitrix24.ru.
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # Unique Bitrix24 portal identifier from OAuth context.
    member_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # Portal registration timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Timestamp of the last portal update.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
