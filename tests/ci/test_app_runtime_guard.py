"""Runtime restart/stop safety guard regressions for issue #61."""
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox

from src.services.app_runtime import AppRuntime
from src.ui.pages.communication_settings_page import CommunicationSettings


class _Controller:
    def __init__(self, running=True):
        self.running = running

    def is_experiment_running(self):
        return self.running


class _ExperimentRuntime:
    def __init__(self, order, stop_result=True):
        self.controller = _Controller()
        self.order = order
        self.stop_result = stop_result

    def get_controller(self):
        return self.controller

    def stop_experiment(self):
        self.order.append("stop_experiment")
        if self.stop_result:
            self.controller.running = False
        return self.stop_result

    def cleanup(self):
        self.order.append("experiment_cleanup")


class _Stoppable:
    def __init__(self, order, name):
        self.order = order
        self.name = name

    def stop(self):
        self.order.append(self.name)

    def stop_all(self):
        self.order.append(self.name)


def _started_runtime(stop_result=True):
    order = []
    runtime = AppRuntime()
    runtime._started = True
    runtime.experiment_runtime = _ExperimentRuntime(order, stop_result)
    runtime.data_handler = _Stoppable(order, "data_handler")
    runtime.device_manager = _Stoppable(order, "devices")
    return runtime, order


def test_runtime_stop_finishes_experiment_before_cleanup_and_ports():
    runtime, order = _started_runtime(stop_result=True)

    assert runtime.stop() is True

    assert order == [
        "stop_experiment",
        "experiment_cleanup",
        "data_handler",
        "devices",
    ]
    assert runtime.is_started is False


def test_runtime_stop_aborts_without_teardown_when_experiment_stop_fails():
    runtime, order = _started_runtime(stop_result=False)

    assert runtime.stop() is False

    assert order == ["stop_experiment"]
    assert runtime.is_started is True
    assert runtime.experiment_runtime is not None
    assert runtime.data_handler is not None
    assert runtime.device_manager is not None


def test_runtime_restart_does_not_start_new_services_after_guard_failure():
    runtime, order = _started_runtime(stop_result=False)
    runtime.start = Mock()

    assert runtime.restart() is False

    runtime.start.assert_not_called()
    assert order == ["stop_experiment"]


def test_saved_settings_report_not_applied_when_runtime_guard_fails(monkeypatch):
    information = Mock()
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "information", information)
    monkeypatch.setattr(QMessageBox, "critical", critical)
    apply_callback = Mock(return_value=False)
    page = SimpleNamespace(
        _sync_widgets_to_settings=Mock(),
        communication_service=SimpleNamespace(save=Mock()),
        _dirty=True,
        logger=Mock(),
        _apply_callback=apply_callback,
        runtime=None,
    )

    CommunicationSettings._on_save(page)

    page.communication_service.save.assert_called_once_with()
    apply_callback.assert_called_once_with()
    critical.assert_called_once()
    information.assert_not_called()
    assert page._dirty is False
