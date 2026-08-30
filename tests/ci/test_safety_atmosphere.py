"""Safety-atmosphere write-result regressions for issue #62."""
from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox

from src.controllers.experiment_controller import ExperimentController
from src.models.experiment_state import ExperimentPhase
from src.ui.pages.integrated_control_page import IntegratedControlPage


class _FlowDevice:
    def __init__(self, failing_gases=()):
        self.failing_gases = set(failing_gases)
        self.calls = []

    def set_flow(self, gas, flow):
        self.calls.append((gas, flow))
        return gas not in self.failing_gases


def test_safety_atmosphere_retries_and_emits_high_visibility_alert():
    device = _FlowDevice(failing_gases={"CO", "H2"})
    controller = ExperimentController(device_manager=device)
    alerts = []
    statuses = []
    messages = []
    controller.safety_alert.connect(alerts.append)
    controller.status_updated.connect(statuses.append)
    controller.system_message_updated.connect(messages.append)

    assert controller._set_safety_atmosphere() is False

    attempts = Counter(gas for gas, _ in device.calls)
    assert attempts == {"N2": 1, "CO": 3, "CO2": 1, "H2": 3}
    assert len(alerts) == 1
    assert "CO" in alerts[0] and "H2" in alerts[0]
    assert "人工" in alerts[0]
    assert statuses[-1] == "危险：安全气氛设置失败"
    assert messages[-1] == alerts[0]


def test_failed_safety_atmosphere_never_broadcasts_success():
    device = _FlowDevice(failing_gases={"H2"})
    controller = ExperimentController(device_manager=device)
    messages = []
    controller.system_message_updated.connect(messages.append)
    controller.state_machine.transition_to(ExperimentPhase.CONFIGURING)
    controller.state_machine.transition_to(ExperimentPhase.RUNNING)

    result = controller._finish_experiment_common(
        "实验已停止",
        "用户手动停止实验，已切换到N₂保护",
    )

    assert result is False
    assert any("安全气氛设置失败" in message for message in messages)
    assert all("已切换到N₂保护" not in message for message in messages)


def test_safety_atmosphere_success_writes_each_channel_once():
    device = _FlowDevice()
    controller = ExperimentController(device_manager=device)

    assert controller._set_safety_atmosphere() is True
    assert device.calls == [
        ("N2", controller.SAFETY_N2_FLOW_LPM),
        ("CO", 0.0),
        ("CO2", 0.0),
        ("H2", 0.0),
    ]


def test_safety_alert_reaches_status_log_and_critical_dialog(monkeypatch):
    critical = Mock()
    monkeypatch.setattr(QMessageBox, "critical", critical)
    view = SimpleNamespace(
        logger=Mock(),
        experiment_status=Mock(),
        _current_system_message="",
    )
    message = "安全气氛设置失败（H2），请立即人工处置。"

    IntegratedControlPage._on_safety_alert(view, message)

    view.logger.critical.assert_called_once()
    view.experiment_status.set_status.assert_called_once_with(
        experiment_status=message
    )
    critical.assert_called_once_with(view, "气体安全告警", message)
    assert view._current_system_message == message
