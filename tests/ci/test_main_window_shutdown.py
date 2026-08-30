"""Regression coverage for the application shutdown safety path (issue #60)."""
import sys
from types import SimpleNamespace
from types import ModuleType
from unittest.mock import Mock

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except ImportError:
    webengine_stub = ModuleType("PySide6.QtWebEngineWidgets")
    webengine_stub.QWebEngineView = QWidget
    sys.modules["PySide6.QtWebEngineWidgets"] = webengine_stub

from src.ui.main_window import MainWindow


_APP = QApplication.instance() or QApplication([])


class _WindowHarness(MainWindow):
    def __init__(self, experiment_api, runtime):
        QMainWindow.__init__(self)
        self.logger = Mock()
        self.comm_settings_page = None
        self.integrated_control_page = None
        self.ui_dependencies = SimpleNamespace(experiment_api=experiment_api)
        self.runtime = runtime


def _confirm_exit(monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.Yes,
    )


def test_close_event_stops_running_experiment_before_runtime(monkeypatch):
    _confirm_exit(monkeypatch)
    shutdown_order = []
    experiment_api = Mock()
    experiment_api.is_experiment_running.return_value = True
    experiment_api.stop_experiment.side_effect = (
        lambda: shutdown_order.append("experiment") or True
    )
    runtime = Mock()
    runtime.stop.side_effect = lambda: shutdown_order.append("runtime")
    window = _WindowHarness(experiment_api, runtime)
    event = QCloseEvent()

    window.closeEvent(event)

    experiment_api.stop_experiment.assert_called_once_with()
    runtime.stop.assert_called_once_with()
    assert shutdown_order == ["experiment", "runtime"]
    assert event.isAccepted()


def test_close_event_blocks_shutdown_when_experiment_stop_fails(monkeypatch):
    _confirm_exit(monkeypatch)
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    experiment_api = Mock()
    experiment_api.is_experiment_running.return_value = True
    experiment_api.stop_experiment.return_value = False
    runtime = Mock()
    window = _WindowHarness(experiment_api, runtime)
    event = QCloseEvent()

    window.closeEvent(event)

    critical.assert_called_once()
    runtime.stop.assert_not_called()
    assert not event.isAccepted()


def test_close_event_does_not_stop_idle_experiment(monkeypatch):
    _confirm_exit(monkeypatch)
    experiment_api = Mock()
    experiment_api.is_experiment_running.return_value = False
    runtime = Mock()
    window = _WindowHarness(experiment_api, runtime)
    event = QCloseEvent()

    window.closeEvent(event)

    experiment_api.stop_experiment.assert_not_called()
    runtime.stop.assert_called_once_with()
    assert event.isAccepted()
