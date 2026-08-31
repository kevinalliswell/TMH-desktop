"""Safety net for the sampling -> SQLite persistence chain (issues #76, #77).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
from datetime import datetime
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from src.device_clients.data_handler import DataHandler
from src.application.services import HistoryQueryService, ReportExportService
from src.services.gb13241_calculator import ReductionCalculator
from src.services.database import ExperimentData, ExperimentDatabase


@pytest.fixture()
def db(tmp_path):
    database = ExperimentDatabase(str(tmp_path / "experiments.db"))
    assert database.create_experiment(
        ExperimentData(
            experiment_id="EXP-1",
            experiment_name="安全网",
            sample_name="样品A",
            sample_weight=500.0,
            start_time="2026-08-29 10:00:00",
        )
    )
    return database


def _row(**overrides):
    row = dict(
        timestamp="2026-08-29T10:00:01",
        experiment_duration="00:00:01",
        temperature=25.0,
        weight=500.0,
        weight_loss=0.0,
        co_flow=0.0,
        co2_flow=0.0,
        n2_flow=5.0,
        h2_flow=0.0,
    )
    row.update(overrides)
    return row


def test_valid_row_is_persisted_baseline(db):
    assert db.add_experiment_data("EXP-1", _row()) is True
    assert len(db.get_experiment_data("EXP-1")) == 1


def test_database_rejects_none_flow_at_storage_boundary(db):
    assert db.add_experiment_data("EXP-1", _row(h2_flow=None)) is False
    assert db.get_experiment_data("EXP-1") == []


def test_none_flow_preserves_sample_with_invalid_quality_flag(tmp_path, db):
    handler = DataHandler(
        str(tmp_path / "device-data.db"),
        save_interval=1,
        experiment_db=db,
    )
    sampled_at = datetime(2026, 8, 29, 10, 0, 1).timestamp()
    state = SimpleNamespace(
        experiment_id="EXP-1",
        initial_weight=500.0,
        experiment_start_time=sampled_at - 1,
    )
    handler.set_state_machine(
        SimpleNamespace(is_running=True, get_state=lambda: state)
    )
    frame = SimpleNamespace

    handler._save_experiment_data_point(
        {
            "frames": {
                "temperature": frame(payload={"temperatures": {"T8": 25.0}}),
                "weight": frame(payload={"weight": 500.0}),
                "flows": {
                    "CO": frame(payload={"pv": 1.0}),
                    "CO2": frame(payload={"pv": 2.0}),
                    "N2": frame(payload={"pv": 5.0}),
                    "H2": frame(payload={"pv": None}),
                },
            }
        },
        sampled_at,
    )

    rows = db.get_experiment_data("EXP-1")
    assert len(rows) == 1
    assert rows[0]["temperature"] == 25.0
    assert rows[0]["weight"] == 500.0
    assert rows[0]["h2_flow"] == 0.0
    assert rows[0]["data_quality"] == {
        "temperature": True,
        "weight": True,
        "flows": {"CO": True, "CO2": True, "N2": True, "H2": False},
    }


def _handler(tmp_path, db, sampled_at):
    handler = DataHandler(
        str(tmp_path / "device-data.db"),
        save_interval=1,
        experiment_db=db,
    )
    state = SimpleNamespace(
        experiment_id="EXP-1",
        initial_weight=500.0,
        experiment_start_time=sampled_at - 1,
    )
    handler.set_state_machine(
        SimpleNamespace(is_running=True, get_state=lambda: state)
    )
    return handler


def _sample(handler, sampled_at, weight):
    frame = SimpleNamespace
    handler._save_experiment_data_point(
        {
            "frames": {
                "temperature": frame(payload={"temperatures": {"T8": 900.0}}),
                "weight": frame(payload={"weight": weight}),
                "flows": {
                    "CO": frame(payload={"pv": 4.5}),
                    "CO2": frame(payload={"pv": 3.0}),
                    "N2": frame(payload={"pv": 7.5}),
                    "H2": frame(payload={"pv": 0.0}),
                },
            }
        },
        sampled_at,
    )


def test_weight_columns_are_nullable_after_schema_migration(tmp_path):
    legacy_path = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_path) as connection:
        connection.execute(
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
                system_message TEXT,
                data_quality TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO experiment_data (
                experiment_id, timestamp, temperature, weight, weight_loss,
                co_flow, co2_flow, n2_flow, h2_flow
            ) VALUES ('EXP-1', '2026-08-29T10:00:00', 25, 500, 0, 0, 0, 5, 0)
            """
        )

    database = ExperimentDatabase(str(legacy_path))
    with sqlite3.connect(legacy_path) as connection:
        columns = {
            row[1]: row[3]
            for row in connection.execute("PRAGMA table_info(experiment_data)")
        }

    assert columns["weight"] == 0
    assert columns["weight_loss"] == 0
    assert database.get_experiment_data("EXP-1")[0]["weight"] == 500.0
    assert database.add_experiment_data(
        "EXP-1",
        _row(
            timestamp="2026-08-29T10:01:00",
            weight=None,
            weight_loss=None,
        ),
    )
    migrated_rows = database.get_experiment_data("EXP-1")
    assert [row["weight"] for row in migrated_rows] == [500.0, None]


def test_mid_run_balance_dropout_is_invalid_not_100_percent_loss(tmp_path, db):
    sampled_at = datetime(2026, 8, 29, 10, 0).timestamp()
    handler = _handler(tmp_path, db, sampled_at)
    _sample(handler, sampled_at, 500.0)
    _sample(handler, sampled_at + 60, None)
    _sample(handler, sampled_at + 120, 490.0)

    rows = db.get_experiment_data("EXP-1")
    assert len(rows) == 3
    assert rows[1]["weight"] is None
    assert rows[1]["weight_loss"] is None
    assert rows[1]["data_quality"]["weight"] is False

    analysis = ReductionCalculator().analyze_experiment_data(
        [
            {
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "weight": row["weight"],
            }
            for row in rows
        ],
        total_iron_content=60.0,
        feo_content=10.0,
    )
    assert analysis["initial_weight"] == 500.0
    assert analysis["final_weight"] == 490.0
    assert analysis["data_points"] == 2


def test_startup_balance_dropout_does_not_crash_report(tmp_path, db):
    sampled_at = datetime(2026, 8, 29, 10, 0).timestamp()
    handler = _handler(tmp_path, db, sampled_at)
    _sample(handler, sampled_at, None)

    rows = db.get_experiment_data("EXP-1")
    assert rows[0]["weight"] is None
    assert ReductionCalculator().analyze_experiment_data(
        [{"timestamp": sampled_at, "weight": rows[0]["weight"]}],
        total_iron_content=60.0,
        feo_content=10.0,
    ) == {}

    assert db.update_experiment_analysis_results(
        "EXP-1",
        {
            "initial_weight": None,
            "final_weight": None,
            "final_reduction_degree": None,
            "reduction_index": None,
        },
    )
    with sqlite3.connect(db.db_path) as connection:
        connection.execute(
            "UPDATE experiments SET experiment_type = 'reducibility' "
            "WHERE experiment_id = 'EXP-1'"
        )
    resources_dir = Path(__file__).resolve().parents[2] / "resources"
    exporter = ReportExportService(
        history_query_service=HistoryQueryService(repository=db),
        exports_dir=str(tmp_path / "exports"),
        resources_dir=str(resources_dir),
    )
    detail = exporter.history_query_service.get_experiment_detail("EXP-1")
    assert detail.weights == [None]
    assert detail.weight_losses == [None]

    txt_path = tmp_path / "exports" / "dropout.txt"
    exporter.export_experiment_data("EXP-1", str(txt_path), "txt")
    assert "\t无效\t无效\t" in txt_path.read_text(encoding="utf-8")

    report_path = Path(exporter.generate_html_report("EXP-1"))
    assert report_path.exists()
