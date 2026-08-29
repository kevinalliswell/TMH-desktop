"""Safety net for the sampling -> SQLite persistence chain (issues #76, #77).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
import pytest

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


def test_none_flow_rejects_entire_row_KNOWN_BUG_76(db):
    # data_handler builds {"PV": None} frames when a single MFC read fails and
    # None reaches the NOT NULL co/co2/n2/h2_flow columns: the INSERT fails and
    # the whole sample (temperature and weight included) is lost. The #76 fix
    # must coerce/flag upstream in data_handler; this test pins the DB-side
    # mechanism that makes the loss total.
    assert db.add_experiment_data("EXP-1", _row(h2_flow=None)) is False
    assert db.get_experiment_data("EXP-1") == []


def test_none_weight_rejects_entire_row_KNOWN_BUG_77(db):
    # The NOT NULL weight column is why data_handler coerces a balance dropout
    # to weight=0.0 today, fabricating 100% weight-loss samples. The #77 fix
    # must mark such samples invalid instead of inventing 0.0.
    assert db.add_experiment_data("EXP-1", _row(weight=None)) is False
