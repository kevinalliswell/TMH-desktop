"""data_quality must change what downstream code sees, not just sit in the row.

The invalid-sample work stored a per-channel quality map but only one consumer
ever read it, and only its ``weight`` key — redundantly, since an invalid weight
was already stored as NULL. Invalid flows and temperatures were still surfaced
as a real-looking 0.0, which is indistinguishable from 'CO genuinely off' or a
true 0 °C. The reduction clock starts at the first CO flow above zero, so an
early failed CO read silently shifted the origin and every interpolated
timepoint with it.
"""
import sqlite3
from datetime import datetime, timedelta

import pytest

from src.application.services import HistoryQueryService
from src.services.database import ExperimentData, ExperimentDatabase
from src.services.gb13241_calculator import ReductionCalculator


@pytest.fixture()
def db(tmp_path):
    database = ExperimentDatabase(str(tmp_path / "quality.db"))
    assert database.create_experiment(
        ExperimentData(
            experiment_id="EXP-1",
            experiment_name="质量标记",
            sample_name="样品A",
            sample_weight=500.0,
            start_time="2026-08-29 10:00:00",
        )
    )
    return database


def _row(index, *, quality, co=4.5, temperature=900.0):
    return {
        "timestamp": f"2026-08-29T10:{index:02d}:00",
        "experiment_duration": "",
        "temperature": temperature,
        "weight": 500.0 - index,
        "weight_loss": index / 5.0,
        "co_flow": co,
        "co2_flow": 3.0,
        "n2_flow": 7.5,
        "h2_flow": 0.0,
        "data_quality": quality,
    }


ALL_VALID = {
    "temperature": True,
    "weight": True,
    "flows": {"CO": True, "CO2": True, "N2": True, "H2": True},
}
CO_INVALID = {
    "temperature": True,
    "weight": True,
    "flows": {"CO": False, "CO2": True, "N2": True, "H2": True},
}
TEMP_INVALID = {
    "temperature": False,
    "weight": True,
    "flows": {"CO": True, "CO2": True, "N2": True, "H2": True},
}


def test_invalid_flow_is_not_surfaced_as_a_real_zero(db):
    assert db.add_experiment_data("EXP-1", _row(0, quality=CO_INVALID, co=0.0))
    assert db.add_experiment_data("EXP-1", _row(1, quality=ALL_VALID))

    detail = HistoryQueryService(repository=db).get_experiment_detail("EXP-1")

    assert detail.gas_flows["CO"] == [None, 4.5], "读数失效必须以 None 表达，不能是 0.0"
    assert detail.gas_flows["N2"] == [7.5, 7.5]


def test_invalid_temperature_is_not_surfaced_as_a_real_zero(db):
    assert db.add_experiment_data("EXP-1", _row(0, quality=TEMP_INVALID, temperature=0.0))
    assert db.add_experiment_data("EXP-1", _row(1, quality=ALL_VALID))

    detail = HistoryQueryService(repository=db).get_experiment_detail("EXP-1")

    assert detail.temperatures == [None, 900.0], "失效温度不得与真实 0℃ 混淆"


def test_rows_written_before_the_quality_column_are_treated_as_valid(db):
    assert db.add_experiment_data("EXP-1", _row(0, quality={}))

    detail = HistoryQueryService(repository=db).get_experiment_detail("EXP-1")

    assert detail.temperatures == [900.0]
    assert detail.gas_flows["CO"] == [4.5]


# --- the quantified consequence: a shifted reduction origin ------------------


def _series(co_flows):
    started = datetime(2026, 8, 1, 10, 0, 0)
    return [
        {
            "timestamp": started + timedelta(minutes=i),
            "weight": 500.0 - i * 0.5,
            "co_flow": co,
        }
        for i, co in enumerate(co_flows)
    ]


def test_reduction_start_is_flagged_uncertain_when_co_was_unreadable():
    """An unreadable CO sample before the first confirmed flow shifts the origin."""
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([None, None, 4.5, 4.5, 4.5]),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["reduction_start_uncertain"] is True


def test_reduction_start_is_certain_when_every_co_sample_was_readable():
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([0.0, 0.0, 4.5, 4.5, 4.5]),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["reduction_start_uncertain"] is False


def test_unreadable_co_after_the_start_does_not_flag_uncertainty():
    analysis = ReductionCalculator().analyze_experiment_data(
        _series([4.5, None, 4.5, 4.5]),
        total_iron_content=60.0,
        feo_content=1.0,
    )

    assert analysis["reduction_start_uncertain"] is False


# --- exports mark invalid readings -------------------------------------------


def test_exports_mark_invalid_readings_rather_than_leaving_them_blank(db, tmp_path):
    from pathlib import Path

    from src.application.services import ReportExportService

    assert db.add_experiment_data("EXP-1", _row(0, quality=CO_INVALID, co=0.0))

    exporter = ReportExportService(
        history_query_service=HistoryQueryService(repository=db),
        exports_dir=str(tmp_path / "exports"),
        resources_dir=str(Path(__file__).resolve().parents[2] / "resources"),
    )
    target = tmp_path / "exports" / "quality.txt"
    exporter.export_experiment_data("EXP-1", str(target), "txt")

    text = target.read_text(encoding="utf-8")
    assert "无效" in text, "GB 检测记录里，无效读数必须与未填写的空列区分开"
