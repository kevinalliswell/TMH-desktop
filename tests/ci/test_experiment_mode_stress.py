from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from src.device_clients.data_handler import DataHandler
from src.models.experiment_state import ExperimentPhase

from tests.ci.test_experiment_flow_threading import (
    FakeDeviceHub,
    _build_controller,
    _build_workflow,
    _experiment_params,
    _stop_and_cleanup,
    _wait_until,
)


STANDARD_MODE_IDS = (
    "GB_13241_2017",
    "GB_13242_2017",
    "GB_13240_2018",
)

SAFETY_GAS_CALLS = [
    ("N2", 5.0),
    ("CO", 0.0),
    ("CO2", 0.0),
    ("H2", 0.0),
]


def _count_experiments(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]


def _assert_idle_with_stopped_timers(controller) -> None:
    state = controller.state_machine.get_state()
    assert state.phase == ExperimentPhase.IDLE
    assert not controller.is_experiment_running()
    assert not controller.stage_timer.isActive()
    assert not controller.experiment_duration_updater.isActive()


def _force_stage_ready(controller, device_hub: FakeDeviceHub, stage) -> None:
    device_hub.temperature = stage.target_temp
    elapsed_seconds = stage.duration * 60 + 1 if stage.duration > 0 else 1
    controller.state_machine.update_state_silent(
        stage_start_time=controller._clock() - elapsed_seconds
    )


def test_standard_modes_survive_repeated_start_stop_cycles(tmp_path, monkeypatch):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    db_path = tmp_path / "runtime_experiments.db"
    total_cycles = 30

    try:
        for cycle in range(total_cycles):
            mode_id = STANDARD_MODE_IDS[cycle % len(STANDARD_MODE_IDS)]

            assert controller.set_experiment_mode_by_id(mode_id) is True
            assert controller.start_experiment() is True
            assert controller.start_experiment() is False

            QCoreApplication.processEvents()
            assert controller.stop_experiment() is True

            _assert_idle_with_stopped_timers(controller)
            assert device_hub.flow_calls[-4:] == SAFETY_GAS_CALLS

        assert _count_experiments(db_path) == total_cycles
    finally:
        _stop_and_cleanup(controller)


def test_standard_mode_stage_progression_reaches_completion_for_every_mode(
    tmp_path, monkeypatch
):
    for mode_id in STANDARD_MODE_IDS:
        mode_tmp_path = tmp_path / mode_id
        mode_tmp_path.mkdir()
        controller, device_hub = _build_controller(
            mode_tmp_path,
            monkeypatch,
            temperature=25.0,
        )

        try:
            assert controller.set_experiment_mode_by_id(mode_id) is True
            assert controller.start_experiment() is True

            expected_stage_count = len(
                controller.experiment_mode_manager.get_experiment_stages()
            )
            observed_stage_indices = []

            for expected_index in range(expected_stage_count):
                state = controller.state_machine.get_state()
                assert state.phase == ExperimentPhase.RUNNING
                assert state.current_stage_index == expected_index
                assert controller.experiment_mode_manager.current_stage_index == expected_index

                current_stage = (
                    controller.experiment_mode_manager.get_current_stage_settings()
                )
                assert current_stage is not None
                observed_stage_indices.append(expected_index)

                _force_stage_ready(controller, device_hub, current_stage)
                controller.update_experiment_stage()
                QCoreApplication.processEvents()

            assert observed_stage_indices == list(range(expected_stage_count))
            _assert_idle_with_stopped_timers(controller)
            assert device_hub.flow_calls[-4:] == SAFETY_GAS_CALLS
        finally:
            _stop_and_cleanup(controller)


def test_workflow_data_collection_threads_survive_repeated_experiment_sessions(
    tmp_path, monkeypatch
):
    controller, device_hub = _build_controller(tmp_path, monkeypatch, temperature=500.0)
    workflow = _build_workflow(controller, device_hub)
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
        for session_index, mode_id in enumerate(STANDARD_MODE_IDS * 2):
            params = {
                **_experiment_params(),
                "experiment_mode_id": mode_id,
                "project_name": f"Offline Stress {session_index}",
                "sample_id": f"OFFLINE-STRESS-{session_index:03d}",
            }

            handler.start()
            assert handler.is_running is True
            start_result = workflow.start_experiment(params)
            assert start_result.success is True

            assert _wait_until(
                lambda: len(
                    experiment_db.get_experiment_data(start_result.experiment_id)
                )
                > 0,
                timeout_s=2.0,
            )

            stop_result = workflow.stop_experiment()
            assert stop_result.success is True
            handler.stop()

            _assert_idle_with_stopped_timers(controller)
            assert handler.is_running is False
            assert handler.data_thread is None
            assert handler.db_thread is None
            assert device_hub.flow_calls[-4:] == SAFETY_GAS_CALLS

        assert _count_experiments(tmp_path / "runtime_experiments.db") == 6
    finally:
        if handler.is_running:
            handler.stop()
        _stop_and_cleanup(controller)
