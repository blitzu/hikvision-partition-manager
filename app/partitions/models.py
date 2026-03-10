"""Partition-related ORM models: Partition, PartitionCamera, PartitionState,
CameraDetectionSnapshot, CameraDisarmRefcount, PartitionAuditLog."""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Partition(Base):
    __tablename__ = "partitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_rearm_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_if_disarmed_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PartitionCamera(Base):
    """Association table linking partitions to cameras (many-to-many)."""

    __tablename__ = "partition_cameras"

    partition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partitions.id"),
        primary_key=True,
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id"),
        primary_key=True,
    )


class PartitionState(Base):
    __tablename__ = "partition_state"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    partition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partitions.id"),
        nullable=False,
        unique=True,
    )
    state: Mapped[str] = mapped_column(
        Enum(
            "armed",
            "disarmed",
            "error",
            "partial",
            name="partition_state_enum",
        ),
        nullable=False,
        default="armed",
    )
    last_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scheduled_rearm_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class CameraDetectionSnapshot(Base):
    __tablename__ = "camera_detection_snapshot"
    __table_args__ = (UniqueConstraint("camera_id", "partition_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id"),
        nullable=False,
    )
    partition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partitions.id"),
        nullable=False,
    )
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CameraDisarmRefcount(Base):
    """Tracks which partitions have disarmed a camera, with a generated count column.

    The disarm_count column is a PostgreSQL GENERATED ALWAYS AS STORED column
    computed from cardinality(disarmed_by_partitions). It is attached via a
    DDL event listener (for create_all in tests) and also added explicitly in
    the Alembic migration via raw SQL.
    """

    __tablename__ = "camera_disarm_refcount"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id"),
        nullable=False,
        unique=True,
    )
    disarmed_by_partitions: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )


from sqlalchemy import DDL, event  # noqa: E402

event.listen(
    CameraDisarmRefcount.__table__,
    "after_create",
    DDL(
        "ALTER TABLE camera_disarm_refcount "
        "ADD COLUMN disarm_count INTEGER "
        "GENERATED ALWAYS AS (cardinality(disarmed_by_partitions)) STORED"
    ),
)


class PartitionAuditLog(Base):
    __tablename__ = "partition_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    partition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partitions.id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    # Named "audit_metadata" in Python to avoid conflict with SQLAlchemy's
    # reserved DeclarativeBase.metadata attribute; maps to "metadata" column in DB.
    audit_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
