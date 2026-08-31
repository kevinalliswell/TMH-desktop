from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

webengine_stub = ModuleType("PySide6.QtWebEngineWidgets")
webengine_stub.QWebEngineView = QWidget
sys.modules.setdefault("PySide6.QtWebEngineWidgets", webengine_stub)

from src.controllers.experiment_controller import ExperimentController
from src.device_clients.data_handler import DataHandler
from src.services.experiment_facade import ExperimentFacade
from src.services.experiment_runtime import ExperimentRuntime
from src.ui.main_window import MainWindow
from src.ui.pages.experiment_mode_settings_page import ExperimentModeSettingsPage


def _ensure_app():
    return QCoreApplication.instance() or QCoreApplication([])


def test_runtime_get_experiment_data_returns_current_record_without_new_controller():
    runtime = ExperimentRuntime(device_manager=None, data_handler=None)
    record = object()
    runtime._controller = SimpleNamespace(current_experiment=record)
    runtime._signals_connected = True

    assert runtime.get_experiment_data() is record


def test_runtime_and_facade_forward_experiment_completed_signal():
    _ensure_app()
    runtime = ExperimentRuntime(device_manager=None, data_handler=None)
    controller = runtime.ensure_controller()
    facade = ExperimentFacade(runtime)
    events: list[str] = []
    facade.experiment_completed.connect(lambda: events.append("completed"))

    controller.experiment_completed.emit()

    assert events == ["completed"]
    runtime.cleanup()


def test_facade_connect_signals_accepts_separate_completion_callback():
    _ensure_app()
    runtime = ExperimentRuntime(device_manager=None, data_handler=None)
    controller = runtime.ensure_controller()
    facade = ExperimentFacade(runtime)
    events: list[str] = []
    noop = lambda *_args: None
    facade.connect_signals(
        noop,
        noop,
        noop,
        lambda: events.append("stopped"),
        noop,
        noop,
        completed_cb=lambda: events.append("completed"),
    )

    controller.experiment_completed.emit()

    assert events == ["completed"]
    facade.cleanup()


def test_data_handler_no_longer_exposes_state_compatibility_noops():
    obsolete_methods = {
        "set_experiment_running",
        "set_experiment_start_time",
        "set_initial_weight",
        "start_save_db_thread",
        "stop_save_db_thread",
    }

    assert obsolete_methods.isdisjoint(vars(DataHandler))


def test_controller_initial_weight_does_not_write_data_handler_state():
    class _StateCopyTrap:
        def set_initial_weight(self, _weight):
            raise AssertionError("DataHandler must read weight from the state machine")

    _ensure_app()
    controller = ExperimentController(data_handler=_StateCopyTrap())

    controller.set_initial_weight(12.5)

    assert controller.initial_weight == 12.5
    controller.cleanup()


def test_mode_page_reads_gas_limits_from_live_provider():
    limits = {"H2": 5.0, "CO": 5.0}
    page = SimpleNamespace(
        _gas_safety_limits_provider=lambda: limits,
        gas_safety_limits={"H2": 9.0, "CO": 9.0},
    )

    assert ExperimentModeSettingsPage._current_gas_safety_limits(page)["H2"] == 5.0

    limits = {"H2": 1.5, "CO": 2.0}

    assert ExperimentModeSettingsPage._current_gas_safety_limits(page) == limits


def test_apply_comm_settings_rebuilds_only_runtime_facade():
    old_facade = object()
    rebind_calls = []
    runtime_services = SimpleNamespace(
        experiment_runtime=object(),
        device_manager=object(),
        data_handler=object(),
        device_hub=object(),
        experiment_type_manager=object(),
        communication_config=SimpleNamespace(
            mfc=SimpleNamespace(gas_safety_limits={"H2": 1.0, "CO": 2.0})
        ),
    )

    class _Runtime:
        services = runtime_services

        def apply_comm_settings(self):
            pass

    window = SimpleNamespace(
        runtime=_Runtime(),
        runtime_services=None,
        ui_dependencies=SimpleNamespace(
            experiment_api=old_facade,
            experiment_type_manager=runtime_services.experiment_type_manager,
        ),
        integrated_control_page=SimpleNamespace(
            rebind_runtime=lambda *args, **kwargs: rebind_calls.append((args, kwargs))
        ),
        _build_ui_dependencies=lambda: (_ for _ in ()).throw(
            AssertionError("unrelated UI services must not be rebuilt")
        ),
    )

    MainWindow._apply_comm_settings(window)

    assert window.ui_dependencies.experiment_api is not old_facade
    assert len(rebind_calls) == 1
    assert rebind_calls[0][1]["gas_safety_limits"] == {"H2": 1.0, "CO": 2.0}
