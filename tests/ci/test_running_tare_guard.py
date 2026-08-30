"""Running-experiment tare guard regressions for issue #67."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.models.experiment_state import ExperimentPhase
from src.ui.pages.integrated_control_page import IntegratedControlPage
from tests.ci.test_experiment_flow_threading import _build_controller


def test_running_experiment_rejects_tare_without_touching_device_or_baseline(
    tmp_path,
    monkeypatch,
):
    controller, device = _build_controller(tmp_path, monkeypatch)
    messages = []
    controller.system_message_updated.connect(messages.append)
    controller.set_initial_weight(500.123)
    assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
    assert controller.start_experiment() is True
    tare_calls_before = device.tare_calls
    baseline_before = controller.initial_weight

    assert controller.tare_balance(skip_confirmation=True) is False

    assert device.tare_calls == tare_calls_before
    assert controller.initial_weight == pytest.approx(baseline_before)
    assert any("实验运行中禁止天平清零" in message for message in messages)


@pytest.mark.parametrize(
    ("phase", "expected_enabled"),
    [
        (ExperimentPhase.IDLE, True),
        (ExperimentPhase.RUNNING, False),
        (ExperimentPhase.STAGE_TRANSITION, False),
        (ExperimentPhase.STOPPING, False),
    ],
)
def test_tare_button_is_enabled_only_when_idle(phase, expected_enabled):
    view = SimpleNamespace(
        _was_experiment_active=False,
        control_panel=SimpleNamespace(
            start_btn=Mock(),
            stop_btn=Mock(),
            tare_btn=Mock(),
        ),
        experiment_status=Mock(),
        _on_experiment_ended_cleanup=Mock(),
    )
    state = SimpleNamespace(
        phase=phase,
        is_running=phase in (
            ExperimentPhase.RUNNING,
            ExperimentPhase.STAGE_TRANSITION,
        ),
        is_active=phase != ExperimentPhase.IDLE,
        error_message="",
    )

    IntegratedControlPage._on_state_changed(view, state)

    view.control_panel.tare_btn.setEnabled.assert_called_once_with(expected_enabled)
