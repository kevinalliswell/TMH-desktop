from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from src.controllers.experiment_controller import ExperimentController
from src.services.experiment_modes import ExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager
from src.services.standard_modes import STANDARD_MODES, ExperimentType


def test_standard_catalog_drives_mode_and_type_managers():
    mode_manager = ExperimentModeManager()
    type_manager = ExperimentTypeManager(mode_manager=mode_manager)

    assert set(mode_manager.get_standard_modes()) == set(STANDARD_MODES)
    assert set(type_manager.get_standard_types()) == set(STANDARD_MODES)

    for mode_id, definition in STANDARD_MODES.items():
        mode = mode_manager.get_standard_mode(mode_id)
        type_info = type_manager.get_type_by_id(mode_id)

        assert mode["name"] == definition.name
        assert mode["description"] == definition.description
        assert mode["stages"]
        assert type_info.name == definition.name
        assert type_info.description == definition.description


def test_controller_resolves_every_standard_id_through_catalog():
    app = QCoreApplication.instance() or QCoreApplication([])
    mode_manager = ExperimentModeManager()
    type_manager = ExperimentTypeManager(mode_manager=mode_manager)
    controller = ExperimentController(
        experiment_mode_manager=mode_manager,
        experiment_type_manager=type_manager,
    )

    for mode_id, definition in STANDARD_MODES.items():
        assert controller.set_experiment_mode_by_id(mode_id)
        assert controller.current_experiment_type is definition.experiment_type

    controller.cleanup()
    assert app is not None


def test_standard_mode_sample_prefixes_are_centralized():
    assert {
        mode_id: definition.sample_prefix
        for mode_id, definition in STANDARD_MODES.items()
    } == {
        "GB_13241_2017": "RED",
        "GB_13242_2017": "RDI",
        "GB_13240_2018": "SWE",
    }
    assert {definition.experiment_type for definition in STANDARD_MODES.values()} == {
        ExperimentType.REDUCIBILITY,
        ExperimentType.LOW_TEMP_DEGRADATION,
        ExperimentType.FREE_SWELLING,
    }


def test_identity_mapping_compatibility_methods_are_removed():
    assert not hasattr(ExperimentTypeManager, "get_experiment_type_for_mode_id")
    assert not hasattr(ExperimentTypeManager, "get_mode_id_for_experiment_type")
