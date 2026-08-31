"""An interrupted schema migration must not strand the sample history.

Making the weight columns nullable rebuilds experiment_data. ``ALTER TABLE ...
RENAME`` is DDL and autocommits under Python's legacy sqlite3 transaction
handling, so a power loss between the rename and the rebuild left every
historical sample in ``experiment_data_not_null_weights`` while the next start
silently created a fresh empty ``experiment_data`` — and validate_database_
integrity() still reported the database healthy.
"""
import sqlite3

import pytest

from src.services.database import ExperimentDatabase

LEGACY = ExperimentDatabase.LEGACY_WEIGHTS_TABLE


def _legacy_schema_db(path, rows=3):
    """Build a pre-migration database with NOT NULL weight columns."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE experiments (
                experiment_id TEXT PRIMARY KEY,
                experiment_name TEXT NOT NULL,
                sample_name TEXT NOT NULL,
                sample_weight REAL NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                description TEXT,
                operator TEXT,
                experiment_type TEXT,
                analysis_results_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE experiment_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                experiment_duration TEXT,
                temperature REAL NOT NULL,
                weight REAL NOT NULL,
                weight_loss REAL NOT NULL,
                co_flow REAL NOT NULL,
                co2_flow REAL NOT NULL,
                n2_flow REAL NOT NULL,
                h2_flow REAL NOT NULL,
                experiment_status TEXT,
                system_message TEXT
            )
            """
        )
        for i in range(rows):
            conn.execute(
                "INSERT INTO experiment_data (experiment_id, timestamp, temperature,"
                " weight, weight_loss, co_flow, co2_flow, n2_flow, h2_flow)"
                " VALUES ('EXP-1', ?, 900, 500, 0, 4.5, 3.0, 7.5, 0)",
                (f"2026-08-29T10:00:{i:02d}",),
            )


def _row_count(path, table):
    with sqlite3.connect(path) as conn:
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            return None


def test_migration_preserves_every_row(tmp_path):
    db_path = tmp_path / "legacy.db"
    _legacy_schema_db(db_path, rows=5)

    ExperimentDatabase(str(db_path))

    assert _row_count(db_path, "experiment_data") == 5
    assert _row_count(db_path, LEGACY) is None, "迁移完成后不应残留孤儿表"


class _FailingCursor:
    """Delegates to a real cursor but dies on one statement, as a crash would."""

    def __init__(self, cursor, fail_on):
        self._cursor = cursor
        self._fail_on = fail_on

    def execute(self, sql, *args, **kwargs):
        if sql.strip().startswith(self._fail_on):
            raise sqlite3.OperationalError("simulated power loss")
        return self._cursor.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _FailingConnection:
    def __init__(self, conn, fail_on):
        self._conn = conn
        self._fail_on = fail_on

    def cursor(self):
        return _FailingCursor(self._conn.cursor(), self._fail_on)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_migration_is_atomic_when_the_rebuild_fails(tmp_path, monkeypatch):
    """A failure mid-rebuild must roll back, not leave the data renamed away."""
    db_path = tmp_path / "atomic.db"
    _legacy_schema_db(db_path, rows=4)

    real_connect = ExperimentDatabase._connect

    def _connect_that_fails_during_rebuild(self, **kwargs):
        conn = real_connect(self, **kwargs)
        # Only the rebuild opens a connection in autocommit mode.
        if kwargs.get("isolation_level", "") is None:
            return _FailingConnection(conn, "CREATE TABLE experiment_data")
        return conn

    monkeypatch.setattr(ExperimentDatabase, "_connect", _connect_that_fails_during_rebuild)

    with pytest.raises(sqlite3.Error):
        ExperimentDatabase(str(db_path))

    monkeypatch.undo()

    # The rollback must leave the original table in place with all its rows.
    assert _row_count(db_path, "experiment_data") == 4, "重建失败必须回滚，数据不得被改名带走"
    assert _row_count(db_path, LEGACY) is None


def test_startup_recovers_an_orphaned_table_from_a_previous_crash(tmp_path):
    """Simulate the historical failure: renamed away, never rebuilt."""
    db_path = tmp_path / "orphan.db"
    _legacy_schema_db(db_path, rows=7)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"ALTER TABLE experiment_data RENAME TO {LEGACY}")

    assert _row_count(db_path, "experiment_data") is None
    assert _row_count(db_path, LEGACY) == 7

    ExperimentDatabase(str(db_path))

    assert _row_count(db_path, "experiment_data") == 7, "必须回收孤儿表而不是新建空表"
    assert _row_count(db_path, LEGACY) is None


def test_startup_recovers_when_an_empty_table_was_already_created(tmp_path):
    """The worse variant: a later start already made the empty replacement."""
    db_path = tmp_path / "orphan-plus-empty.db"
    _legacy_schema_db(db_path, rows=6)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"ALTER TABLE experiment_data RENAME TO {LEGACY}")

    ExperimentDatabase(str(db_path))  # first start: recovers
    ExperimentDatabase(str(db_path))  # second start: no-op

    assert _row_count(db_path, "experiment_data") == 6
    assert _row_count(db_path, LEGACY) is None


def test_orphan_with_data_on_both_sides_is_kept_for_manual_review(tmp_path):
    db_path = tmp_path / "both.db"
    _legacy_schema_db(db_path, rows=2)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"CREATE TABLE {LEGACY} AS SELECT * FROM experiment_data")

    ExperimentDatabase(str(db_path))

    assert _row_count(db_path, LEGACY) == 2, "两侧都有数据时不得自动丢弃任何一侧"
    assert _row_count(db_path, "experiment_data") == 2


def test_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "idempotent.db"
    _legacy_schema_db(db_path, rows=3)

    for _ in range(3):
        ExperimentDatabase(str(db_path))

    assert _row_count(db_path, "experiment_data") == 3


def test_connections_use_wal_and_a_busy_timeout(tmp_path):
    db = ExperimentDatabase(str(tmp_path / "wal.db"))

    with db._connect() as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert mode.lower() == "wal", "读写并发依赖 WAL，否则历史查询会阻塞 1Hz 采样写入"
    assert timeout == ExperimentDatabase.BUSY_TIMEOUT_MS
