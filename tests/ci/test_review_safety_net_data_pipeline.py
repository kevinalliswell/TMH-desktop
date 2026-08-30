"""Safety net for the sampling -> SQLite persistence chain (issues #76, #77).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.device_clients.data_handler import DataHandler
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


def test_none_weight_rejects_entire_row_KNOWN_BUG_77(db):
    # The NOT NULL weight column is why data_handler coerces a balance dropout
    # to weight=0.0 today, fabricating 100% weight-loss samples. The #77 fix
    # must mark such samples invalid instead of inventing 0.0.
    assert db.add_experiment_data("EXP-1", _row(weight=None)) is False
