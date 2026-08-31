from __future__ import annotations

from datetime import datetime, timedelta

from src.application.services import HistoryQueryService, ReportExportService
from src.device_clients.data_handler import DataHandler
from src.services.database import ExperimentData, ExperimentDatabase
from src.services.gb13240_calculator import FreeExpansionCalculator


class _IdleDeviceManager:
    def get_status(self):
        return {}


def test_data_handler_workers_are_joined_and_cannot_wedge_process_exit(tmp_path):
    """Workers must be joined by stop() AND be unable to block interpreter exit.

    This replaces an earlier assertion that the workers are non-daemon. Being
    non-daemon does not make them joinable — stop() joins them either way, and
    the flush guarantees are covered by the two tests below — but it does hand
    a worker that outlives its 3 s join to threading._shutdown(), which joins
    with no timeout. Combined with AppRuntime.stop() returning early when the
    safety atmosphere cannot be confirmed, that made the process impossible to
    exit in exactly the situation the safety guard exists for.
    """
    handler = DataHandler(
        db_path=str(tmp_path / "samples.db"),
        device_manager=_IdleDeviceManager(),
    )
    handler._data_processing_loop = lambda: handler.stop_event.wait()
    handler._db_saving_loop = lambda: handler.stop_event.wait()

    handler.start()
    try:
        assert handler.data_thread.daemon is True
        assert handler.db_thread.daemon is True
    finally:
        data_thread, db_thread = handler.data_thread, handler.db_thread
        handler.stop()

    # stop() still shuts them down cleanly; daemon is only the last-resort net.
    assert data_thread.is_alive() is False
    assert db_thread.is_alive() is False


def test_db_worker_flushes_buffer_when_stopped(tmp_path):
    handler = DataHandler(db_path=str(tmp_path / "flush.db"))
    handler.stop_event.set()
    handler.data_buffer.put({"weight": 1.0})
    saved = []
    handler._save_data_batch = lambda batch: saved.extend(batch)
    handler._close_thread_db_connection = lambda: None
    handler.logger = __import__("logging").getLogger(__name__)
    handler.save_interval = 60

    handler._db_saving_loop()

    assert saved == [{"weight": 1.0}]
    assert handler.data_buffer.empty()


def test_stop_flushes_sample_enqueued_after_db_worker_exit(tmp_path):
    handler = DataHandler(db_path=str(tmp_path / "late-sample.db"))
    handler.is_running = True
    handler.data_buffer.put({"weight": 2.0})
    saved = []
    handler._save_data_batch = lambda batch: saved.extend(batch)

    handler.stop()

    assert saved == [{"weight": 2.0}]
    assert handler.data_buffer.empty()


def test_history_csv_export_includes_utf8_bom(tmp_path):
    database = ExperimentDatabase(str(tmp_path / "history.db"))
    experiment = ExperimentData(
        experiment_id="exp-bom",
        experiment_name="中文实验",
        sample_name="样品",
        sample_weight=500.0,
        start_time="2026-08-31T10:00:00",
        timestamps=["2026-08-31T10:00:00"],
        temperatures=[900.0],
        weights=[500.0],
        weight_losses=[0.0],
        gas_flows={"CO": [4.5], "CO2": [0.0], "N2": [10.5], "H2": [0.0]},
    )
    assert database.create_experiment(experiment)
    assert database.add_experiment_data(
        experiment.experiment_id,
        {
            "timestamp": experiment.timestamps[0],
            "temperature": 900.0,
            "weight": 500.0,
            "weight_loss": 0.0,
            "co_flow": 4.5,
            "co2_flow": 0.0,
            "n2_flow": 10.5,
            "h2_flow": 0.0,
        },
    )

    history_csv = tmp_path / "history.csv"
    service = ReportExportService(history_query_service=HistoryQueryService(repository=database))
    service.export_experiment_data(experiment.experiment_id, str(history_csv), "csv")

    bom = b"\xef\xbb\xbf"
    assert history_csv.read_bytes().startswith(bom)


def test_free_expansion_validation_uses_its_60_minute_reduction_window():
    started_at = datetime(2026, 8, 31, 10, 0, 0)
    data = [
        {"timestamp": started_at, "temperature": 900.0, "gas_flow": 15.0},
        {
            "timestamp": started_at + timedelta(minutes=60),
            "temperature": 900.0,
            "gas_flow": 15.0,
        },
    ]

    assert FreeExpansionCalculator().validate_experiment_conditions(data) == []


def test_free_expansion_validation_checks_temperature_flow_and_duration():
    started_at = datetime(2026, 8, 31, 10, 0, 0)
    data = [
        {"timestamp": started_at, "temperature": 880.0, "gas_flow": 14.0},
        {
            "timestamp": started_at + timedelta(minutes=59),
            "temperature": 880.0,
            "gas_flow": 14.0,
        },
    ]

    problems = FreeExpansionCalculator().validate_experiment_conditions(data)

    assert "温度控制不稳定，应维持在900±10℃" in problems
    assert "气体流量超出范围，应维持在15±0.5L/min" in problems
    assert "实验时间不足1小时" in problems
