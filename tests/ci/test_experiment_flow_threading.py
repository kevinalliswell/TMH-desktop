from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication

from src.application.services import ExperimentWorkflowService
from src.controllers.experiment_controller import ExperimentController
from src.device_clients.data_handler import DataHandler
from src.models.experiment_state import ExperimentPhase
from src.services.database import ExperimentDatabase
from src.services.experiment_file import ExperimentFile
from src.services.experiment_type_manager import ExperimentTypeManager
from src.utils.path_manager import PathManager


def _ensure_qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def _install_temp_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    config_dir = tmp_path / "configs"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    def get_config_path(filename=None):
        return str(config_dir / filename) if filename else str(config_dir)

    def get_data_path(filename=None):
        return str(data_dir / filename) if filename else str(data_dir)

    monkeypatch.setattr(PathManager, "get_config_path", staticmethod(get_config_path))
    monkeypatch.setattr(PathManager, "get_data_path", staticmethod(get_data_path))

    (config_dir / "exp_settings.config").write_text(
        json.dumps(
            {
                "project_name": "Offline Flow Test",
                "sample_name": "Ore A",
                "sample_id": "RDI-OFFLINE-001",
                "experiment_type": "GB/T 13242-2017 铁矿石低温粉化试验方法",
                "experiment_mode_id": "GB_13242_2017",
                "sample_weight": 523.0,
                "operator": "ci",
                "date": "2026-06-25 00:00:00",
                "notes": "offline experiment flow test",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (config_dir / "comm_config.json").write_text(
        json.dumps(
            {
                "PERFORMANCE_CONFIG": {"data_collection_interval": 0.01},
                "SAMPLING": {"interval_s": 0.02},
            }
        ),
        encoding="utf-8",
    )
    return config_dir, data_dir


def _experiment_params() -> dict:
    return {
        "project_name": "Offline Flow Test",
        "sample_name": "Ore A",
        "sample_id": "RDI-OFFLINE-001",
        "experiment_type": "GB/T 13242-2017 铁矿石低温粉化试验方法",
        "experiment_mode_id": "GB_13242_2017",
        "sample_weight": 523.0,
        "operator": "ci",
        "date": "2026-06-25 00:00:00",
        "notes": "offline experiment flow test",
    }


class FakeDeviceHub:
    def __init__(
        self,
        *,
        temperature: float = 500.0,
        connected: bool = True,
        tare_result: bool = True,
    ):
        self.temperature = temperature
        self.connected = connected
        self.tare_result = tare_result
        self.tare_calls = 0
        self.flow_calls: list[tuple[str, float]] = []
        self.current_flows = {"CO": 0.0, "CO2": 0.0, "N2": 0.0, "H2": 0.0}
        self.setpoints = {"CO": 0.0, "CO2": 0.0, "N2": 0.0, "H2": 0.0}

    def get_all_status(self):
        now = time.time()
        return {
            "Temp": {
                "running": True,
                "connected": True,
                "last_update_ts": now,
                "data": self._temperature_data(now),
            },
            "Balance": {
                "running": True,
                "connected": True,
                "last_update_ts": now,
                "data": {"weight": 500.0, "timestamp": now},
            },
            "MFC": {
                "running": True,
                "connected": True,
                "last_update_ts": now,
                "data": dict(self.current_flows, timestamp=now),
            },
        }

    def get_connection_status(self):
        if self.connected:
            return True, "fake devices", ""
        return False, "", "fake devices disconnected"

    def get_status(self, name: str = None):
        if name is None:
            return self.get_status_legacy()
        return self.get_all_status().get(name, {}).get("data")

    def get_status_legacy(self):
        now = time.time()
        flow_frames = {}
        for gas, pv in self.current_flows.items():
            flow_frames[gas] = SimpleNamespace(
                payload={"gas_type": gas, "pv": pv, "sv": self.setpoints[gas]},
                timestamp=now,
            )

        return {
            "frames": {
                "temperature": SimpleNamespace(
                    payload={"temperatures": self._temperature_data(now)},
                    timestamp=now,
                ),
                "weight": SimpleNamespace(payload={"weight": 500.0}, timestamp=now),
                "flows": flow_frames,
            },
            "timestamp": now,
        }

    def get_snapshots(self):
        return SimpleNamespace(timestamp=time.time(), devices={})

    def set_flow(self, gas: str, value: float) -> bool:
        value = float(value)
        self.flow_calls.append((gas, value))
        self.current_flows[gas] = value
        self.setpoints[gas] = value
        return True

    def tare_balance(self) -> bool:
        self.tare_calls += 1
        return self.tare_result

    def _temperature_data(self, timestamp: float):
        temps = {f"T{i}": self.temperature for i in range(1, 10)}
        temps["timestamp"] = timestamp
        return temps


class ControllerApi:
    def __init__(self, controller: ExperimentController):
        self.controller = controller

    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        return self.controller.set_experiment_mode_by_id(mode_id)

    def start_experiment(self, experiment_record=None) -> bool:
        return self.controller.start_experiment(experiment_record)

    def stop_experiment(self):
        return self.controller.stop_experiment()

    def is_experiment_running(self) -> bool:
        return self.controller.is_experiment_running()

    def get_controller(self) -> ExperimentController:
        return self.controller


def _build_controller(
    tmp_path: Path,
    monkeypatch,
    *,
    temperature: float = 500.0,
    tare_result: bool = True,
):
    _ensure_qt_app()
    _install_temp_paths(monkeypatch, tmp_path)

    device_hub = FakeDeviceHub(temperature=temperature, tare_result=tare_result)
    controller = ExperimentController(device_manager=device_hub)
    controller.exp_db = ExperimentDatabase(str(tmp_path / "runtime_experiments.db"))
    return controller, device_hub


def _build_workflow(controller: ExperimentController, device_hub: FakeDeviceHub):
    return ExperimentWorkflowService(
        device_manager=device_hub,
        experiment_api=ControllerApi(controller),
        experiment_file_manager=ExperimentFile(),
        experiment_type_manager=ExperimentTypeManager(),
        logger=logging.getLogger("test.experiment_flow"),
    )


def _stop_and_cleanup(controller: ExperimentController):
    try:
        if controller.is_experiment_running():
            controller.stop_experiment()
    finally:
        controller.cleanup()


def _count_experiments(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]


def _wait_until(predicate, timeout_s: float = 2.0, interval_s: float = 0.02) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        QCoreApplication.processEvents()
        time.sleep(interval_s)
    return predicate()


def test_controller_start_arms_timers_state_and_first_stage_flows(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True

        state = controller.state_machine.get_state()
        assert state.phase == ExperimentPhase.RUNNING
        assert state.initial_weight == 523.0
        assert state.current_stage_index == 0
        assert state.total_stages == 4
        assert controller.stage_timer.isActive()
        assert controller.experiment_duration_updater.isActive()

        first_stage_flows = dict(device_hub.flow_calls[:4])
        assert first_stage_flows == {"CO": 0.0, "CO2": 0.0, "N2": 5.0, "H2": 0.0}
    finally:
        _stop_and_cleanup(controller)


def test_controller_tare_failure_is_reported_without_resetting_initial_weight(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(
        tmp_path,
        monkeypatch,
        temperature=500.0,
        tare_result=False,
    )
    messages: list[str] = []
    controller.system_message_updated.connect(messages.append)

    try:
        controller.set_initial_weight(123.456)

        assert controller.tare_balance(skip_confirmation=True) is False

        assert device_hub.tare_calls == 1
        assert controller.initial_weight == pytest.approx(123.456)
        assert any("天平清零失败" in message for message in messages)
    finally:
        _stop_and_cleanup(controller)


def test_duplicate_start_is_rejected_without_creating_second_experiment(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    db_path = tmp_path / "runtime_experiments.db"

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True
        first_experiment_id = controller.current_experiment.experiment_id
        flow_call_count = len(device_hub.flow_calls)

        assert controller.start_experiment() is False

        assert controller.current_experiment.experiment_id == first_experiment_id
        assert len(device_hub.flow_calls) == flow_call_count
        assert _count_experiments(db_path) == 1
    finally:
        _stop_and_cleanup(controller)


def test_controller_stop_returns_to_idle_stops_timers_and_sets_safety_gas(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True

        controller.stop_experiment()

        state = controller.state_machine.get_state()
        assert state.phase == ExperimentPhase.IDLE
        assert not controller.stage_timer.isActive()
        assert not controller.experiment_duration_updater.isActive()
        assert device_hub.flow_calls[-4:] == [
            ("N2", 5.0),
            ("CO", 0.0),
            ("CO2", 0.0),
            ("H2", 0.0),
        ]
    finally:
        _stop_and_cleanup(controller)


def test_final_stage_completion_returns_to_idle_and_sets_safety_gas(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True

        stages = controller.experiment_mode_manager.get_experiment_stages()
        final_stage_index = len(stages) - 1
        controller.experiment_mode_manager.current_stage_index = final_stage_index
        device_hub.temperature = stages[final_stage_index].target_temp
        controller.state_machine.update_state_silent(
            current_stage_index=final_stage_index,
            stage_start_time=controller._clock() - 1,
        )

        controller.update_experiment_stage()

        assert controller.state_machine.get_state().phase == ExperimentPhase.IDLE
        assert not controller.stage_timer.isActive()
        assert not controller.experiment_duration_updater.isActive()
        assert device_hub.flow_calls[-4:] == [
            ("N2", 5.0),
            ("CO", 0.0),
            ("CO2", 0.0),
            ("H2", 0.0),
        ]
    finally:
        _stop_and_cleanup(controller)


def test_data_handler_threads_save_experiment_rows_and_join_cleanly(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    experiment_db = controller.exp_db
    handler = DataHandler(
        str(tmp_path / "device_data.db"),
        save_interval=0.05,
        device_manager=device_hub,
        experiment_db=experiment_db,
        state_machine=controller.state_machine,
        snapshot_provider=device_hub,
    )
    handler.data_collection_interval = 0.01
    handler.sampling_interval = 0.02
    controller.set_data_handler(handler)

    try:
        handler.start()
        first_data_thread = handler.data_thread
        first_db_thread = handler.db_thread
        handler.start()

        assert handler.data_thread is first_data_thread
        assert handler.db_thread is first_db_thread
        assert handler.data_thread.is_alive()
        assert handler.db_thread.is_alive()

        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True
        experiment_id = controller.current_experiment.experiment_id

        assert _wait_until(
            lambda: len(experiment_db.get_experiment_data(experiment_id)) > 0,
            timeout_s=2.0,
        )

        controller.stop_experiment()
        handler.stop()

        assert handler.is_running is False
        assert handler.data_thread is None
        assert handler.db_thread is None
    finally:
        if handler.is_running:
            handler.stop()
        _stop_and_cleanup(controller)


def test_workflow_stop_reports_success_when_controller_stops(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    workflow = _build_workflow(controller, device_hub)

    try:
        assert workflow.start_experiment(_experiment_params()).success is True

        stop_result = workflow.stop_experiment()

        assert stop_result.success is True
        assert controller.state_machine.get_state().phase == ExperimentPhase.IDLE
    finally:
        _stop_and_cleanup(controller)


def test_workflow_start_result_uses_runtime_experiment_id(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    workflow = _build_workflow(controller, device_hub)

    try:
        start_result = workflow.start_experiment(_experiment_params())

        assert start_result.success is True
        assert start_result.experiment_id == controller.current_experiment.experiment_id
    finally:
        _stop_and_cleanup(controller)


def test_start_failure_after_timers_arm_restores_idle_and_safety_gas(
    tmp_path, monkeypatch
):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)

    def fail_first_stage():
        raise RuntimeError("stage setup failed")

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        monkeypatch.setattr(controller, "execute_current_experiment_stage", fail_first_stage)

        assert controller.start_experiment() is False

        assert controller.state_machine.get_state().phase == ExperimentPhase.IDLE
        assert not controller.stage_timer.isActive()
        assert not controller.experiment_duration_updater.isActive()
        assert device_hub.flow_calls[-4:] == [
            ("N2", 5.0),
            ("CO", 0.0),
            ("CO2", 0.0),
            ("H2", 0.0),
        ]
    finally:
        _stop_and_cleanup(controller)


def test_empty_custom_program_is_rejected_before_record_or_signals(tmp_path, monkeypatch):
    controller, _device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    db_path = tmp_path / "runtime_experiments.db"
    lifecycle_events: list[str] = []
    controller.experiment_started.connect(lambda: lifecycle_events.append("started"))
    controller.experiment_completed.connect(lambda: lifecycle_events.append("completed"))

    try:
        controller.current_experiment_type = None
        controller.current_experiment_type_name = "Empty custom program"
        monkeypatch.setattr(controller.experiment_mode_manager, "is_custom_mode", lambda: True)
        monkeypatch.setattr(
            controller.experiment_mode_manager,
            "get_experiment_stages",
            lambda: [],
        )

        assert controller.start_experiment() is False

        assert controller.state_machine.get_state().phase == ExperimentPhase.IDLE
        assert lifecycle_events == []
        assert _count_experiments(db_path) == 0
    finally:
        _stop_and_cleanup(controller)


def test_controller_uses_monotonic_clock_for_elapsed_time(tmp_path, monkeypatch):
    controller, _device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    clock = iter((100.0, 100.0, 130.0))
    monkeypatch.setattr(controller, "_clock", lambda: next(clock), raising=False)

    try:
        assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
        assert controller.start_experiment() is True
        assert controller.state_machine.get_state().stage_start_time == pytest.approx(100.0)

        stage_info = controller.get_detailed_stage_info()

        assert stage_info["elapsed_time_seconds"] == pytest.approx(30.0)
    finally:
        _stop_and_cleanup(controller)


def test_manual_initial_weight_rejects_reentrant_invocation(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    nested_results: list[bool] = []

    def request_weight(*_args):
        nested_results.append(controller.manual_set_initial_weight())
        return 12.5, True

    controller.set_interaction_callbacks(input_double_callback=request_weight)

    try:
        assert controller.manual_set_initial_weight() is True

        assert nested_results == [False]
        assert device_hub.tare_calls == 1
        assert controller.initial_weight == pytest.approx(12.5)
    finally:
        _stop_and_cleanup(controller)


def test_mode_configuration_failure_removes_precreated_experiment_file(
    tmp_path, monkeypatch
):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    workflow = _build_workflow(controller, device_hub)
    monkeypatch.setattr(workflow.experiment_api, "set_experiment_mode_by_id", lambda _mode: False)

    try:
        start_result = workflow.start_experiment(_experiment_params())

        assert start_result.success is False
        assert start_result.experiment_file_path
        assert not Path(start_result.experiment_file_path).exists()
    finally:
        _stop_and_cleanup(controller)
