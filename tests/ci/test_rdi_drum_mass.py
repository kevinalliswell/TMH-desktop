from __future__ import annotations

from PySide6.QtWidgets import QApplication

from src.application.dto import ExperimentDetailDTO
from src.application.services.report_export_service import ReportExportService
from src.services.gb13242_calculator import LowTempDegradationCalculator
from src.ui.dialogs.rdi_analysis_dialog import (
    RDIAnalysisDialog,
    suggest_drum_sample_weight,
)


def test_rdi_uses_post_reduction_drum_sample_mass_as_denominator():
    result = LowTempDegradationCalculator().calculate_rdi(
        drum_sample_weight=485.0,
        sieve_weights={6.301: 300.0, 3.151: 100.0, 0.501: 45.0, 0.499: 40.0},
    )

    assert result["RDI-0.5"] == 8.25


def test_latest_positive_reduction_weight_is_suggested_for_drum_mass():
    data_points = [
        {"weight": 500.0},
        {"weight": None},
        {"weight": 485.0},
        {"weight": 0.0},
    ]

    assert suggest_drum_sample_weight(data_points, fallback=500.0) == 485.0


def test_rdi_dialog_returns_explicit_drum_sample_mass():
    app = QApplication.instance() or QApplication([])
    dialog = RDIAnalysisDialog(
        experiment_name="RDI",
        initial_weight_g=500.0,
        drum_sample_weight_g=485.0,
    )
    dialog.mass_gt_6_3_spinbox.setValue(300.0)
    dialog.mass_3_15_to_6_3_spinbox.setValue(100.0)
    dialog.mass_0_5_to_3_15_spinbox.setValue(45.0)
    dialog.mass_lt_0_5_spinbox.setValue(40.0)

    dialog.accept()

    assert dialog.get_data()["drum_sample_weight_g"] == 485.0
    assert dialog.result() == dialog.DialogCode.Accepted
    assert app is not None


def test_rdi_report_uses_drum_mass_in_results_table(tmp_path):
    service = ReportExportService(
        history_query_service=object(),
        exports_dir=str(tmp_path),
        resources_dir="resources",
    )
    detail = ExperimentDetailDTO(
        experiment_id="EXP-RDI",
        experiment_name="RDI",
        sample_name="sample",
        sample_weight=500.0,
        start_time="2026-08-31T10:00:00",
        experiment_type="GB/T 13242",
        analysis_results={
            "drum_sample_weight_g": 485.0,
            "sieve_input_masses": {
                "mass_gt_6_3": 300.0,
                "mass_3_15_to_6_3": 100.0,
                "mass_0_5_to_3_15": 45.0,
                "mass_lt_0_5": 40.0,
            },
            "calculated_rdi_indices": {"RDI-3.15": 17.53, "RDI-0.5": 8.25},
        },
    )

    content = service._build_rdi_report(detail)

    assert "<td>485.00</td><td>400.00</td>" in content
    assert "入鼓试样质量" in content
    assert "m<sub>2</sub> / m<sub>0</sub>" in content
