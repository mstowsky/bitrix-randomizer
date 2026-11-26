"""SQLAlchemy models for Bitrix Randomizer."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, func
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

    # Unique Bitrix24 portal identifier.
    member_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # Encrypted OAuth access token.
    access_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Encrypted OAuth refresh token.
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Access token expiration timestamp.
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Portal REST API endpoint.
    client_endpoint: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Bitrix24 OAuth server endpoint.
    server_endpoint: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Granted REST API scopes.
    scope: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Encrypted application token for event verification.
    application_token_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Whether the portal connection is active.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Timestamp when the portal connection was revoked.
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
