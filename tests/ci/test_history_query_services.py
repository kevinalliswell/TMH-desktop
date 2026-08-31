from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.application.dto import ExperimentDetailDTO
from src.application.services import HistoryQueryService, ReportExportService
from src.services.database import ExperimentData, ExperimentDatabase
from src.ui.pages.history_query_page import HistoryQuery


def _seed_database(db_path: Path) -> ExperimentDatabase:
    database = ExperimentDatabase(str(db_path))
    experiment = ExperimentData(
        experiment_id="exp-001",
        experiment_name="RDI Test",
        sample_name="Ore A",
        sample_weight=500.0,
        start_time="2026-04-17T10:00:00",
        end_time="2026-04-17T11:00:00",
        description="history service test",
        operator="tester",
        experiment_type="RDI",
        analysis_results_json=json.dumps(
            {
                "initial_sample_weight_g": 500.0,
                "sieve_input_masses": {
                    "mass_gt_6_3": 200.0,
                    "mass_3_15_to_6_3": 160.0,
                    "mass_0_5_to_3_15": 100.0,
                    "mass_lt_0_5": 40.0,
                },
                "calculated_rdi_indices": {
                    "RDI+3.15": 72.0,
                    "RDI-0.5": 8.0,
                },
            }
        ),
    )
    assert database.create_experiment(experiment) is True
    assert database.add_experiment_data(
        experiment.experiment_id,
        {
            "timestamp": "2026-04-17T10:00:00",
            "temperature": 25.0,
            "weight": 500.0,
            "weight_loss": 0.0,
            "co_flow": 1.0,
            "co2_flow": 2.0,
            "n2_flow": 3.0,
            "h2_flow": 4.0,
        },
    ) is True
    assert database.add_experiment_data(
        experiment.experiment_id,
        {
            "timestamp": "2026-04-17T10:10:00",
            "temperature": 100.0,
            "weight": 490.0,
            "weight_loss": 2.0,
            "co_flow": 1.5,
            "co2_flow": 2.5,
            "n2_flow": 3.5,
            "h2_flow": 4.5,
        },
    ) is True
    return database


def test_history_query_service_loads_summaries_and_detail(tmp_path):
    database = _seed_database(tmp_path / "history.db")
    service = HistoryQueryService(repository=database)

    summaries = service.list_experiments()
    assert len(summaries) == 1
    assert summaries[0].experiment_name == "RDI Test"

    detail = service.get_experiment_detail("exp-001")
    assert detail is not None
    assert detail.sample_name == "Ore A"
    assert detail.timestamps == ["2026-04-17T10:00:00", "2026-04-17T10:10:00"]
    assert detail.gas_flows["N2"] == [3.0, 3.5]
    assert detail.analysis_results["calculated_rdi_indices"]["RDI-0.5"] == 8.0


def test_report_export_service_writes_csv_and_html_report(tmp_path):
    database = _seed_database(tmp_path / "export.db")
    history_service = HistoryQueryService(repository=database)
    resources_dir = Path(__file__).resolve().parents[2] / "resources"
    export_service = ReportExportService(
        history_query_service=history_service,
        exports_dir=str(tmp_path / "exports"),
        resources_dir=str(resources_dir),
    )

    csv_path = tmp_path / "exports" / "history.csv"
    written_csv = export_service.export_experiment_data("exp-001", str(csv_path), "csv")
    assert Path(written_csv).exists()
    assert "RDI Test" in csv_path.read_text(encoding="utf-8")

    html_path = Path(export_service.generate_html_report("exp-001"))
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "Ore A" in html_content
    assert "28.00" in html_content
    assert "72.00" not in html_content


def test_report_export_service_writes_report_to_selected_directory(tmp_path):
    database = _seed_database(tmp_path / "selected-directory.db")
    resources_dir = Path(__file__).resolve().parents[2] / "resources"
    export_service = ReportExportService(
        history_query_service=HistoryQueryService(repository=database),
        exports_dir=str(tmp_path / "exports"),
        reports_dir=str(tmp_path / "default-reports"),
        resources_dir=str(resources_dir),
    )
    selected_dir = tmp_path / "operator-selected"

    html_path = Path(
        export_service.generate_html_report("exp-001", output_dir=selected_dir)
    )

    assert html_path.parent == selected_dir
    assert html_path.exists()


def test_default_report_directory_uses_dedicated_downloads_folder(tmp_path):
    export_service = ReportExportService(
        history_query_service=object(),
        exports_dir=str(tmp_path / "exports"),
        reports_dir=str(tmp_path / "Downloads" / "TMH-Exp-Datas"),
    )

    report_dir = Path(export_service.default_report_dir())

    assert report_dir == tmp_path / "Downloads" / "TMH-Exp-Datas"
    assert report_dir.is_dir()


def test_history_page_passes_selected_report_directory(monkeypatch, tmp_path):
    selected_dir = tmp_path / "selected"
    calls = []

    class ReportService:
        def default_report_dir(self):
            return str(tmp_path / "Downloads" / "TMH-Exp-Datas")

        def generate_html_report(self, experiment_id, output_dir=None):
            calls.append((experiment_id, output_dir))
            return str(Path(output_dir) / "report.html")

    page = SimpleNamespace(
        current_experiment={"experiment_id": "exp-001", "experiment_name": "RDI Test"},
        report_export_service=ReportService(),
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(selected_dir),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    HistoryQuery.generate_report(page)

    assert calls == [("exp-001", str(selected_dir))]


def test_nonstandard_experiment_generates_generic_html_report(tmp_path):
    detail = ExperimentDetailDTO(
        experiment_id="custom-001",
        experiment_name="Custom Cycle",
        sample_name="Ore B",
        sample_weight=420.0,
        start_time="2026-08-31T09:00:00",
        end_time="2026-08-31T09:10:00",
        operator="operator",
        experiment_type="CUSTOM",
        description="operator-defined cycle",
        timestamps=["2026-08-31T09:00:00"],
        temperatures=[800.0],
        weights=[419.0],
        weight_losses=[0.24],
        gas_flows={"CO": [1.0], "CO2": [2.0], "N2": [3.0], "H2": [0.0]},
    )
    history_service = SimpleNamespace(
        get_experiment_detail=lambda experiment_id: detail if experiment_id == "custom-001" else None
    )
    export_service = ReportExportService(
        history_query_service=history_service,
        reports_dir=str(tmp_path),
    )

    report_path = Path(export_service.generate_html_report("custom-001"))
    content = report_path.read_text(encoding="utf-8")

    assert "Custom Cycle" in content
    assert "CUSTOM" in content
    assert "800.0" in content
