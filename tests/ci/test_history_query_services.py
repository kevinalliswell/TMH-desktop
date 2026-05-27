from __future__ import annotations

import json
from pathlib import Path

from src.application.services import HistoryQueryService, ReportExportService
from src.services.database import ExperimentData, ExperimentDatabase


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
    assert "72.00" in html_content
