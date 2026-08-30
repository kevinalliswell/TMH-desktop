"""Regression tests for the shared experiment-mode dependency graph."""

from __future__ import annotations

import json

from PySide6.QtCore import QCoreApplication

from src.controllers.experiment_controller import ExperimentController
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.app_runtime import AppRuntime
from src.services.experiment_runtime import ExperimentRuntime
from src.services.experiment_type_manager import ExperimentTypeManager
from src.services.experiment_modes import ExperimentStage
from src.utils.path_manager import PathManager


def _custom_mode(target_temp: float) -> dict:
    return {
        "name": "实时自定义模式",
        "description": "shared-manager regression",
        "category": "custom",
        "enabled": True,
        "stages": [
            {
                "stage_name": "HEATING",
                "description": "shared heating",
                "target_temp": target_temp,
                "temp_tolerance": 5.0,
                "duration": 10.0,
                "heating_rate": 10.0,
                "gas_settings": {
                    "CO": 0.0,
                    "CO2": 0.0,
                    "N2": 5.0,
                    "H2": 0.0,
                    "total_flow": 5.0,
                },
            }
        ],
    }


def _shared_runtime(tmp_path, monkeypatch):
    config_path = tmp_path / "experiment_modes.json"
    config_path.write_text(
        json.dumps({"experiment_modes": {"custom_modes": {}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        PathManager,
        "get_config_path",
        staticmethod(lambda _name: str(config_path)),
    )

    mode_manager = EnhancedExperimentModeManager()
    type_manager = ExperimentTypeManager(mode_manager=mode_manager)
    runtime = ExperimentRuntime(
        device_manager=None,
        data_handler=None,
        experiment_mode_manager=mode_manager,
        experiment_type_manager=type_manager,
    )
    return runtime, mode_manager, type_manager


def test_runtime_injects_one_manager_pair_into_controller(tmp_path, monkeypatch):
    QCoreApplication.instance() or QCoreApplication([])
    runtime, mode_manager, type_manager = _shared_runtime(tmp_path, monkeypatch)

    controller = runtime.ensure_controller()

    assert controller.experiment_mode_manager is mode_manager
    assert controller.experiment_type_manager is type_manager
    assert type_manager.experiment_mode_manager is mode_manager


def test_app_runtime_owns_one_manager_pair_for_its_full_lifetime():
    app_runtime = AppRuntime()

    assert isinstance(
        app_runtime.experiment_mode_manager,
        EnhancedExperimentModeManager,
    )
    assert (
        app_runtime.experiment_type_manager.experiment_mode_manager
        is app_runtime.experiment_mode_manager
    )
    experiment_runtime = app_runtime._create_experiment_runtime(None, None, None)
    assert (
        experiment_runtime.experiment_mode_manager
        is app_runtime.experiment_mode_manager
    )
    assert (
        experiment_runtime.experiment_type_manager
        is app_runtime.experiment_type_manager
    )


def test_create_and_edit_are_immediately_visible_to_controller(tmp_path, monkeypatch):
    QCoreApplication.instance() or QCoreApplication([])
    runtime, mode_manager, type_manager = _shared_runtime(tmp_path, monkeypatch)
    controller: ExperimentController = runtime.ensure_controller()
    mode_id = "CUSTOM_LIVE"

    assert mode_manager.add_custom_mode(mode_id, _custom_mode(500.0)) is True
    runtime.reload_experiment_modes()

    assert type_manager.is_custom_type(mode_id) is True
    assert controller.set_experiment_mode_by_id(mode_id) is True
    first_stage = controller.experiment_mode_manager.get_current_stage_settings()
    assert first_stage.stage is ExperimentStage.HEATING
    assert first_stage.target_temp == 500.0

    assert mode_manager.update_custom_mode(mode_id, _custom_mode(650.0)) is True
    runtime.reload_experiment_modes()

    assert controller.set_experiment_mode_by_id(mode_id) is True
    edited_stage = controller.experiment_mode_manager.get_current_stage_settings()
    assert edited_stage.stage is ExperimentStage.HEATING
    assert edited_stage.target_temp == 650.0


def test_reload_does_not_mutate_an_active_experiment_program(tmp_path, monkeypatch):
    runtime, mode_manager, _type_manager = _shared_runtime(tmp_path, monkeypatch)
    mode_id = "CUSTOM_SNAPSHOT"
    assert mode_manager.add_custom_mode(mode_id, _custom_mode(500.0)) is True
    runtime.reload_experiment_modes()
    assert mode_manager.set_custom_experiment_mode(mode_id) is True
    assert mode_manager.get_current_stage_settings().target_temp == 500.0

    assert mode_manager.update_custom_mode(mode_id, _custom_mode(650.0)) is True
    runtime.reload_experiment_modes()

    # The active run keeps its start-time snapshot; selecting the mode for a
    # later run picks up the edited definition.
    assert mode_manager.get_current_stage_settings().target_temp == 500.0
    assert mode_manager.set_custom_experiment_mode(mode_id) is True
    assert mode_manager.get_current_stage_settings().target_temp == 650.0


def test_standard_definition_lookup_is_independent_of_active_custom_state(
    tmp_path,
    monkeypatch,
):
    runtime, mode_manager, type_manager = _shared_runtime(tmp_path, monkeypatch)
    mode_id = "CUSTOM_ACTIVE"
    assert mode_manager.add_custom_mode(mode_id, _custom_mode(500.0)) is True
    runtime.reload_experiment_modes()
    assert mode_manager.set_custom_experiment_mode(mode_id) is True

    standard_stages = type_manager.get_type_stages("GB_13241_2017")

    assert standard_stages[0]["target_temp"] == 900.0
