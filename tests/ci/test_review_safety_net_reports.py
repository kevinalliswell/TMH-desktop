"""Safety net for GB report generation (review issues #74, #75).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
from pathlib import Path

import pytest

from src.application.dto import ExperimentDetailDTO
from src.application.services.report_export_service import ReportExportService

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


@pytest.mark.xfail(strict=True, reason="#74: the RDI+3.15 value is printed under the RDI-3.15 label")
def test_rdi_report_conclusion_uses_minus_3_15_expected(service):
    detail = _detail(
        experiment_type="GB/T 13242",
        analysis_results={
            "calculated_rdi_indices": {"RDI+3.15": 72.0, "RDI-3.15": 28.0, "RDI-0.5": 8.0},
        },
    )
    content = service._build_rdi_report(detail)
    assert "RDI-3.15为28.00%" in content
    assert "RDI-3.15为72.00%" not in content


@pytest.mark.xfail(
    strict=True,
    reason="#75: missing analysis falls back to invented RI=1.67 and mass_after=mass_before*0.95",
)
def test_reducibility_report_does_not_invent_results_expected(service):
    content = service._build_reducibility_report(
        _detail(experiment_type="GB/T 13241", analysis_results=None)
    )
    # 1.67 is the fabricated final-reduction-degree default; 475.0 is the
    # fabricated mass_after (500g * 0.95). Neither may appear as a measurement.
    assert "1.67" not in content
    assert "475.0" not in content
