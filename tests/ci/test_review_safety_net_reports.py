"""Safety net for GB report generation (review issues #74, #75).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.application.dto import ExperimentDetailDTO
from src.application.services.report_export_service import ReportExportService
from src.services.gb13241_calculator import ReductionCalculator
from src.services.gb13242_calculator import LowTempDegradationCalculator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def service(tmp_path):
    return ReportExportService(
        history_query_service=object(),
        exports_dir=str(tmp_path),
        resources_dir=str(PROJECT_ROOT / "resources"),
    )


def _detail(**overrides):
    kwargs = dict(
        experiment_id="EXP-1",
        experiment_name="安全网试验",
        sample_name="样品A",
        sample_weight=500.0,
        start_time="2026-08-01 10:00:00",
        end_time="2026-08-01 13:00:00",
        operator="tester",
    )
    kwargs.update(overrides)
    return ExperimentDetailDTO(**kwargs)


def test_rdi_report_conclusion_uses_minus_3_15(service):
    detail = _detail(
        experiment_type="GB/T 13242",
        analysis_results={
            "calculated_rdi_indices": {"RDI+3.15": 72.0, "RDI-3.15": 28.0, "RDI-0.5": 8.0},
        },
    )
    content = service._build_rdi_report(detail)
    assert "RDI-3.15为28.00%" in content
    assert "RDI-3.15为72.00%" not in content


def test_rdi_calculator_returns_minus_3_15():
    result = LowTempDegradationCalculator().calculate_rdi(
        100.0,
        {6.301: 60.0, 3.151: 12.0, 0.501: 20.0, 0.499: 8.0},
    )

    assert result["RDI+3.15"] == 72.0
    assert result["RDI-3.15"] == 28.0
    assert result["RDI-0.5"] == 8.0


def test_rdi_report_derives_minus_3_15_for_legacy_results(service):
    detail = _detail(
        experiment_type="GB/T 13242",
        analysis_results={"calculated_rdi_indices": {"RDI+3.15": 72.0, "RDI-0.5": 8.0}},
    )

    content = service._build_rdi_report(detail)

    assert "RDI-3.15为28.00%" in content


def test_rdi_report_marks_missing_indices_as_unmeasured(service):
    content = service._build_rdi_report(
        _detail(experiment_type="GB/T 13242", analysis_results={})
    )

    assert "RDI-3.15未测得" in content
    assert "RDI-0.5未测得" in content
    assert "RDI-3.15为72.00%" not in content


def _measured_reducibility_detail(**overrides):
    kwargs = {
        "experiment_type": "GB/T 13241",
        "analysis_results": {
            "total_iron_content": 20.0 / 0.430,
            "feo_content": 0.0,
            "initial_sample_weight": 100.0,
        },
        "timestamps": [
            "2026-08-01T10:00:00",
            "2026-08-01T10:10:00",
            "2026-08-01T11:10:00",
            "2026-08-01T11:50:00",
        ],
        "weights": [100.0, 100.0, 88.0, 80.0],
        "gas_flows": {
            "CO": [0.0, 4.5, 4.5, 4.5],
            "CO2": [0.0, 0.0, 0.0, 0.0],
            "N2": [5.0, 10.5, 10.5, 10.5],
            "H2": [0.0, 0.0, 0.0, 0.0],
        },
    }
    kwargs.update(overrides)
    return _detail(**kwargs)


def test_reducibility_report_does_not_invent_results(service):
    content = service._build_reducibility_report(
        _detail(experiment_type="GB/T 13241", analysis_results=None)
    )
    # 1.67 is the fabricated final-reduction-degree default; 475.0 is the
    # fabricated mass_after (500g * 0.95). Neither may appear as a measurement.
    assert "1.67" not in content
    assert "475.0" not in content
    assert "未测得" in content


def test_reducibility_metrics_interpolate_measured_series(service):
    metrics = service._calculate_reducibility_metrics(_measured_reducibility_detail())

    assert metrics["mass_before"] == pytest.approx(100.0)
    assert metrics["mass_after"] == pytest.approx(80.0)
    assert metrics["oxygen_loss_30"] == pytest.approx(6.0)
    assert metrics["oxygen_loss_60"] == pytest.approx(12.0)
    assert metrics["oxygen_loss_90"] == pytest.approx(18.0)
    assert metrics["reduction_degree_30"] == pytest.approx(30.0)
    assert metrics["reduction_degree_60"] == pytest.approx(60.0)
    assert metrics["reduction_degree_90"] == pytest.approx(90.0)
    assert metrics["reduction_degree_final"] == pytest.approx(100.0)
    assert metrics["reduction_rate"] == pytest.approx(1.0)
    assert metrics["t40"] == pytest.approx(40.0)
    assert metrics["t50"] == pytest.approx(50.0)
    assert metrics["t70"] == pytest.approx(70.0)


def test_reducibility_report_renders_only_measured_results(service):
    content = service._build_reducibility_report(_measured_reducibility_detail())

    assert "<td>6.00</td><td>12.00</td><td>18.00</td><td>20.00</td>" in content
    assert "<td>30.00</td><td>60.00</td><td>90.00</td><td>100.00</td>" in content
    assert "最终还原度为100.00%" in content
    assert "test_results[" not in content


def test_reducibility_metrics_do_not_extrapolate_missing_timepoints(service):
    detail = _measured_reducibility_detail(
        timestamps=[
            "2026-08-01T10:00:00",
            "2026-08-01T10:10:00",
            "2026-08-01T11:10:00",
        ],
        weights=[100.0, 100.0, 88.0],
        gas_flows={
            "CO": [0.0, 4.5, 4.5],
            "CO2": [0.0, 0.0, 0.0],
            "N2": [5.0, 10.5, 10.5],
            "H2": [0.0, 0.0, 0.0],
        },
    )

    metrics = service._calculate_reducibility_metrics(detail)

    assert metrics["reduction_degree_60"] == pytest.approx(60.0)
    assert metrics["reduction_degree_90"] is None
    assert metrics["oxygen_loss_90"] is None


def test_reducibility_metrics_require_observed_reducing_gas(service):
    detail = _measured_reducibility_detail(
        gas_flows={
            "CO": [0.0, 0.0, 0.0, 0.0],
            "CO2": [0.0, 0.0, 0.0, 0.0],
            "N2": [5.0, 5.0, 5.0, 5.0],
            "H2": [0.0, 0.0, 0.0, 0.0],
        }
    )

    metrics = service._calculate_reducibility_metrics(detail)

    assert metrics["mass_before"] is None
    assert metrics["reduction_degree_final"] is None


def test_reduction_analysis_persists_chemistry_and_recorded_sample_weight():
    started = datetime(2026, 8, 1, 10, 0, 0)
    analysis = ReductionCalculator().analyze_experiment_data(
        [
            {"timestamp": started, "weight": 99.5},
            {"timestamp": started + timedelta(minutes=60), "weight": 90.0},
        ],
        total_iron_content=60.0,
        feo_content=25.0,
        initial_sample_weight=100.0,
    )

    assert analysis["total_iron_content"] == pytest.approx(60.0)
    assert analysis["feo_content"] == pytest.approx(25.0)
    assert analysis["initial_weight"] == pytest.approx(100.0)
    assert analysis["total_weight_loss"] == pytest.approx(10.0)
    assert analysis["final_reduction_degree"] == pytest.approx(49.52)
