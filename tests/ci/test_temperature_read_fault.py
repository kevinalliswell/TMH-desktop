"""Sample-temperature fault handling regressions for issue #65."""
import time
from types import SimpleNamespace
from unittest.mock import Mock

from src.controllers.experiment_controller import ExperimentController
from src.models.experiment_state import ExperimentPhase


class _TemperatureDevice:
    def __init__(self, value=None):
        self.value = value

    def get_status(self):
        temperature_frame = None
        if self.value is not None:
            temperature_frame = SimpleNamespace(
                payload={"temperatures": {"T8": self.value}}
            )
        return {"frames": {"temperature": temperature_frame}}


def _running_controller(device):
    controller = ExperimentController(device_manager=device)
    stage = SimpleNamespace(
        stage=SimpleNamespace(value="冷却"),
        description="宽容差冷却",
        target_temp=25.0,
        temp_tolerance=30.0,
        duration=0,
        heating_rate=-5.0,
    )
    controller.experiment_mode_manager.get_current_stage_settings = lambda: stage
    controller.experiment_mode_manager.get_experiment_stages = lambda: [stage]
    controller.experiment_mode_manager.current_stage_index = 0
    controller.experiment_mode_manager.can_advance_stage = Mock(return_value=False)
    controller.state_machine.transition_to(ExperimentPhase.CONFIGURING)
    controller.state_machine.transition_to(
        ExperimentPhase.RUNNING,
        stage_start_time=time.time() - 10,
    )
    return controller


def test_missing_temperature_is_none_but_real_zero_is_valid():
    device = _TemperatureDevice(None)
    controller = ExperimentController(device_manager=device)

    assert controller.get_sample_temperature() is None

    device.value = float("nan")
    assert controller.get_sample_temperature() is None

    device.value = 0.0
    assert controller.get_sample_temperature() == 0.0


def test_missing_temperature_pauses_stage_evaluation_and_alerts_once():
    device = _TemperatureDevice(None)
    controller = _running_controller(device)
    alerts = []
    statuses = []
    controller.safety_alert.connect(alerts.append)
    controller.status_updated.connect(statuses.append)

    for _ in range(controller.TEMP_READ_FAILURE_ALERT_THRESHOLD + 1):
        controller.update_experiment_stage()

    controller.experiment_mode_manager.can_advance_stage.assert_not_called()
    assert len(alerts) == 1
    assert "连续" in alerts[0] and "阶段判定已暂停" in alerts[0]
    assert statuses[-1] == "危险：样品温度读取失败"
    assert controller.state_machine.phase == ExperimentPhase.RUNNING


def test_valid_temperature_resets_fault_counter_and_resumes_evaluation():
    device = _TemperatureDevice(None)
    controller = _running_controller(device)
    for _ in range(controller.TEMP_READ_FAILURE_ALERT_THRESHOLD):
        controller.update_experiment_stage()

    device.value = 0.0
    controller.update_experiment_stage()

    controller.experiment_mode_manager.can_advance_stage.assert_called_once()
    args = controller.experiment_mode_manager.can_advance_stage.call_args.args
    assert args[0] == 0.0
    assert controller._temperature_read_failures == 0
    assert controller._temperature_fault_alerted is False
