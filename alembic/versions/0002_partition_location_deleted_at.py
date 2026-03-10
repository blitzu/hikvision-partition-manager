"""Add location_id and deleted_at to partitions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10

Adds:
  - partitions.location_id (UUID FK -> locations, nullable)
  - partitions.deleted_at (TIMESTAMPTZ, nullable) for soft-delete
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "partitions",
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "partitions",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("partitions", "deleted_at")
    op.drop_column("partitions", "location_id")
