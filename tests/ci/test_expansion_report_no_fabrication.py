"""The GB/T 13240 swelling report must not fabricate a certificate.

The #74/#75 work rewrote the RDI and reducibility reports to print 未测得 for
anything unmeasured, but _build_expansion_report was left untouched: with no
analysis at all it printed a swelling index of 20.00%, an unconditional
'符合标准要求' verdict, and a visual inspection ('无裂纹', '强度良好') that
nobody performed.
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
        experiment_id="EXP-SWELL",
        experiment_name="自由膨胀试验",
        sample_name="球团A",
        sample_weight=500.0,
        start_time="2026-08-01 10:00:00",
        end_time="2026-08-01 13:00:00",
        operator="tester",
        experiment_type="GB/T 13240",
    )
    kwargs.update(overrides)
    return ExperimentDetailDTO(**kwargs)


def test_unanalysed_swelling_experiment_reports_nothing_as_measured(service):
    content = service._build_expansion_report(_detail(analysis_results={}))

    # The fabricated defaults must be gone.
    assert "20.00" not in content
    assert "120.0" not in content
    assert "自由膨胀指数未测得" in content


def test_unanalysed_swelling_experiment_does_not_certify_conformity(service):
    content = service._build_expansion_report(_detail(analysis_results=None))

    assert "符合标准要求" not in content


def test_visual_inspection_is_never_invented(service):
    content = service._build_expansion_report(_detail(analysis_results={}))

    assert "球团表面光滑，无明显缺陷" not in content
    assert "无裂纹" not in content
    assert "强度良好" not in content
    assert "未记录" in content


def test_chemical_composition_is_not_invented(service):
    content = service._build_expansion_report(_detail(analysis_results={}))

    for fabricated in ("65.5", "0.3", "4.2", "0.29"):
        assert fabricated not in content


def test_measured_swelling_results_are_rendered(service):
    content = service._build_expansion_report(
        _detail(
            analysis_results={
                "initial_volume": 500.0,
                "final_volume": 600.0,
                "expansion_index": 20.0,
                "chemical_composition": {"TFe": "64.1"},
                "pellet_description": [
                    {
                        "pellet_no": 1,
                        "appearance": "表面粗糙",
                        "cracks": "轻微裂纹",
                        "strength_evaluation": "中等",
                    }
                ],
            }
        )
    )

    assert "自由膨胀指数为20.00%" in content
    assert "64.1" in content
    assert "轻微裂纹" in content
    assert "未记录" not in content


def test_swelling_index_is_derived_when_only_volumes_are_recorded(service):
    content = service._build_expansion_report(
        _detail(analysis_results={"initial_volume": 500.0, "final_volume": 600.0})
    )

    assert "自由膨胀指数为20.00%" in content


def test_rdi_report_does_not_invent_the_drum_mass(service):
    content = service._build_rdi_report(
        _detail(experiment_type="GB/T 13242", sample_weight=0.0, analysis_results={})
    )

    assert "500.00" not in content
    assert "未测得" in content
