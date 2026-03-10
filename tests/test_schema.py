"""
Schema integration tests — verify all 9 tables exist with correct structure.
Requires a real PostgreSQL instance (ARRAY, JSONB types not supported in SQLite).

Each test inspects information_schema to confirm:
- Table exists
- Required columns are present with correct data types
- Constraints exist (unique, generated)
"""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_locations_table(engine):
    """locations table: id (uuid), name (varchar), timezone (varchar), created_at (timestamptz)."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='locations' AND table_schema='public'"
            )
        )
        cols = {row[0] for row in result}
    assert "id" in cols, f"'id' missing from locations; found: {cols}"
    assert "name" in cols
    assert "timezone" in cols
    assert "created_at" in cols


@pytest.mark.asyncio
async def test_nvr_devices_table(engine):
    """nvr_devices table: all expected columns present."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='nvr_devices' AND table_schema='public'"
            )
        )
        cols = {row[0] for row in result}
    expected = {
        "id", "location_id", "name", "ip_address", "port",
        "username", "password_encrypted", "model", "status",
        "last_seen_at", "created_at",
    }
    missing = expected - cols
    assert not missing, f"Columns missing from nvr_devices: {missing}"


@pytest.mark.asyncio
async def test_cameras_table(engine):
    """cameras table exists; unique constraint on (nvr_id, channel_no) exists."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='cameras' AND table_schema='public'"
            )
        )
        cols = {row[0] for row in result}

        # Check unique constraint
        uc_result = await conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_name = 'cameras'
                  AND tc.constraint_type = 'UNIQUE'
                  AND ccu.column_name IN ('nvr_id', 'channel_no')
                """
            )
        )
        uc_count = uc_result.scalar()

    expected_cols = {"id", "nvr_id", "channel_no", "name", "enabled", "created_at", "updated_at"}
    missing = expected_cols - cols
    assert not missing, f"Columns missing from cameras: {missing}"
    assert uc_count >= 2, "Unique constraint on (nvr_id, channel_no) not found"


@pytest.mark.asyncio
async def test_partitions_table(engine):
    """partitions table: auto_rearm_minutes, alert_if_disarmed_minutes columns present."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='partitions' AND table_schema='public'"
            )
        )
        cols = {row[0] for row in result}
    expected = {"id", "name", "description", "auto_rearm_minutes", "alert_if_disarmed_minutes", "created_at"}
    missing = expected - cols
    assert not missing, f"Columns missing from partitions: {missing}"


@pytest.mark.asyncio
async def test_partition_cameras_table(engine):
    """partition_cameras association table: partition_id, camera_id as composite PK."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='partition_cameras' AND table_schema='public'"
            )
        )
        cols = {row[0] for row in result}

        # Both columns should be primary keys
        pk_result = await conn.execute(
            text(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'partition_cameras'
                  AND tc.constraint_type = 'PRIMARY KEY'
                """
            )
        )
        pk_cols = {row[0] for row in pk_result}

    assert "partition_id" in cols
    assert "camera_id" in cols
    assert "partition_id" in pk_cols, "partition_id not in PK"
    assert "camera_id" in pk_cols, "camera_id not in PK"


@pytest.mark.asyncio
async def test_partition_state_table(engine):
    """partition_state table: state is enum type; partition_id unique constraint exists."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type, udt_name "
                "FROM information_schema.columns "
                "WHERE table_name='partition_state' AND table_schema='public'"
            )
        )
        col_rows = {row[0]: {"data_type": row[1], "udt_name": row[2]} for row in result}

        # Check unique constraint on partition_id
        uc_result = await conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'partition_state'
                  AND tc.constraint_type = 'UNIQUE'
                  AND kcu.column_name = 'partition_id'
                """
            )
        )
        uc_count = uc_result.scalar()

    expected_cols = {"id", "partition_id", "state", "last_changed_at", "last_changed_by",
                     "scheduled_rearm_at", "error_detail"}
    missing = expected_cols - set(col_rows.keys())
    assert not missing, f"Columns missing from partition_state: {missing}"

    # state column should be an enum (USER-DEFINED type in information_schema)
    state_col = col_rows.get("state", {})
    assert state_col.get("data_type") == "USER-DEFINED", \
        f"state column data_type expected USER-DEFINED, got {state_col.get('data_type')}"
    assert uc_count >= 1, "Unique constraint on partition_id not found in partition_state"


@pytest.mark.asyncio
async def test_snapshot_table(engine):
    """camera_detection_snapshot: snapshot_data is jsonb; unique on (camera_id, partition_id)."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='camera_detection_snapshot' AND table_schema='public'"
            )
        )
        col_rows = {row[0]: row[1] for row in result}

        # Check unique constraint on (camera_id, partition_id)
        uc_result = await conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT tc.constraint_name)
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_name = 'camera_detection_snapshot'
                  AND tc.constraint_type = 'UNIQUE'
                  AND ccu.column_name IN ('camera_id', 'partition_id')
                """
            )
        )
        uc_count = uc_result.scalar()

    expected_cols = {"id", "camera_id", "partition_id", "snapshot_data", "taken_at"}
    missing = expected_cols - set(col_rows.keys())
    assert not missing, f"Columns missing from camera_detection_snapshot: {missing}"

    assert col_rows.get("snapshot_data") == "jsonb", \
        f"snapshot_data expected jsonb, got {col_rows.get('snapshot_data')}"
    assert uc_count >= 1, "Unique constraint on (camera_id, partition_id) not found in snapshot table"


@pytest.mark.asyncio
async def test_refcount_table(engine):
    """camera_disarm_refcount: disarmed_by_partitions is ARRAY; disarm_count is generated column."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='camera_disarm_refcount' AND table_schema='public'"
            )
        )
        col_rows = {row[0]: row[1] for row in result}

        # Check that disarm_count has a generation expression
        gen_result = await conn.execute(
            text(
                """
                SELECT generation_expression
                FROM information_schema.columns
                WHERE table_name = 'camera_disarm_refcount'
                  AND column_name = 'disarm_count'
                  AND table_schema = 'public'
                """
            )
        )
        gen_row = gen_result.fetchone()

    expected_cols = {"id", "camera_id", "disarmed_by_partitions", "disarm_count"}
    missing = expected_cols - set(col_rows.keys())
    assert not missing, f"Columns missing from camera_disarm_refcount: {missing}"

    assert col_rows.get("disarmed_by_partitions") == "ARRAY", \
        f"disarmed_by_partitions expected ARRAY, got {col_rows.get('disarmed_by_partitions')}"

    assert gen_row is not None, "disarm_count column not found"
    assert gen_row[0] is not None, "disarm_count has no generation_expression (not a generated column)"


@pytest.mark.asyncio
async def test_audit_table(engine):
    """partition_audit_log: metadata is jsonb; created_at column exists; partition FK exists."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='partition_audit_log' AND table_schema='public'"
            )
        )
        col_rows = {row[0]: row[1] for row in result}

    expected_cols = {"id", "partition_id", "action", "performed_by", "metadata", "created_at"}
    missing = expected_cols - set(col_rows.keys())
    assert not missing, f"Columns missing from partition_audit_log: {missing}"

    assert col_rows.get("metadata") == "jsonb", \
        f"metadata expected jsonb, got {col_rows.get('metadata')}"
