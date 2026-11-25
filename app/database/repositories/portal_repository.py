"""Repository for Bitrix24 portal database operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Portal


class PortalRepository:
    """Provide database operations for connected Bitrix24 portals."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository with a database session."""
        self.db = db

    def get_by_id(self, portal_id: UUID) -> Portal | None:
        """Get a portal by its internal ID."""
        return self.db.get(Portal, portal_id)

    def get_by_domain(self, domain: str) -> Portal | None:
        """Get a portal by its domain."""
        statement = select(Portal).where(Portal.domain == domain)
        return self.db.scalar(statement)

    def get_by_member_id(self, member_id: str) -> Portal | None:
        """Get a portal by its Bitrix24 member ID."""
        statement = select(Portal).where(Portal.member_id == member_id)
        return self.db.scalar(statement)

    def create(self, portal: Portal) -> Portal:
        """Add a new portal to the database."""
        self.db.add(portal)
        self.db.flush()
        return portal

    def update(self, portal: Portal, **values: object) -> Portal:
        """Update portal attributes."""
        for key, value in values.items():
            if not hasattr(portal, key):
                raise ValueError(f"Unknown portal attribute: {key}")
            setattr(portal, key, value)

        self.db.flush()
        return portal

    def delete(self, portal: Portal) -> None:
        """Delete a portal from the database."""
        self.db.delete(portal)
        self.db.flush()
