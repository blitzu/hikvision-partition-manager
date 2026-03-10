"""initial schema — all 9 tables

Revision ID: 0001
Revises:
Create Date: 2026-03-10

Creates all 9 tables in FK-dependency order:
  1. locations
  2. nvr_devices (FK -> locations)
  3. cameras (FK -> nvr_devices) + UniqueConstraint(nvr_id, channel_no)
  4. partitions
  5. partition_cameras (FK -> partitions, cameras)
  6. partition_state (FK -> partitions) + partition_state_enum
  7. camera_detection_snapshot (FK -> cameras, partitions) + JSONB + UniqueConstraint
  8. camera_disarm_refcount (FK -> cameras) + ARRAY(UUID) + GENERATED ALWAYS AS STORED
  9. partition_audit_log (FK -> partitions) + JSONB metadata
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. locations
    op.create_table(
        "locations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 2. nvr_devices (FK -> locations)
    op.create_table(
        "nvr_devices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="8000"),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_encrypted", sa.String(512), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 3. cameras (FK -> nvr_devices) + unique (nvr_id, channel_no)
    op.create_table(
        "cameras",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "nvr_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nvr_devices.id"),
            nullable=False,
        ),
        sa.Column("channel_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("nvr_id", "channel_no", name="uq_cameras_nvr_channel"),
    )

    # 4. partitions
    op.create_table(
        "partitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("auto_rearm_minutes", sa.Integer(), nullable=True),
        sa.Column("alert_if_disarmed_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # 5. partition_cameras association table (FK -> partitions, cameras)
    op.create_table(
        "partition_cameras",
        sa.Column(
            "partition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("partitions.id"),
            primary_key=True,
        ),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id"),
            primary_key=True,
        ),
    )

    # 6. partition_state (FK -> partitions) + enum type
    # Let op.create_table handle enum type creation automatically (create_type=True default).
    # Avoids deprecated op.get_bind() pattern that breaks with newer Alembic/asyncpg.
    op.create_table(
        "partition_state",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "partition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("partitions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "armed",
                "disarmed",
                "error",
                "partial",
                name="partition_state_enum",
            ),
            nullable=False,
            server_default="armed",
        ),
        sa.Column(
            "last_changed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_changed_by", sa.String(255), nullable=True),
        sa.Column(
            "scheduled_rearm_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )

    # 7. camera_detection_snapshot (FK -> cameras, partitions) + JSONB + unique
    op.create_table(
        "camera_detection_snapshot",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id"),
            nullable=False,
        ),
        sa.Column(
            "partition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("partitions.id"),
            nullable=False,
        ),
        sa.Column("snapshot_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "taken_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "camera_id", "partition_id", name="uq_snapshot_camera_partition"
        ),
    )

    # 8. camera_disarm_refcount (FK -> cameras) + ARRAY(UUID)
    # disarm_count is added as GENERATED ALWAYS AS STORED via raw SQL
    # (SQLAlchemy Computed() has known issues with asyncpg + cardinality())
    op.create_table(
        "camera_disarm_refcount",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "disarmed_by_partitions",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
    )
    op.execute(
        """
        ALTER TABLE camera_disarm_refcount
        ADD COLUMN disarm_count INTEGER
        GENERATED ALWAYS AS (cardinality(disarmed_by_partitions)) STORED
        """
    )

    # 9. partition_audit_log (FK -> partitions) + JSONB metadata
    op.create_table(
        "partition_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "partition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("partitions.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("performed_by", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Drop in reverse FK-dependency order
    op.drop_table("partition_audit_log")
    op.drop_table("camera_disarm_refcount")
    op.drop_table("camera_detection_snapshot")
    op.drop_table("partition_state")

    # Drop the enum type after the table that uses it
    op.execute(sa.text("DROP TYPE partition_state_enum"))

    op.drop_table("partition_cameras")
    op.drop_table("partitions")
    op.drop_table("cameras")
    op.drop_table("nvr_devices")
    op.drop_table("locations")
