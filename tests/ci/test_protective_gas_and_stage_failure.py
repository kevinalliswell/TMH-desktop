"""Regressions for the two gas-safety holes found reviewing the integration branch.

1. ``ExperimentWorkflowService.apply_protective_gas`` (the 实验重置 button) was a
   second, unverified copy of the protective-gas purge: it discarded every
   ``set_flow`` result and always reported success.
2. ``_set_stage_gas_flows`` skipped unconfirmed writes as "开发模式" whenever
   ``is_connected`` was False — but that flag is live device health, so a real
   bus loss let an experiment keep running with the wrong atmosphere.
"""
import logging

import pytest

from src.application.services.experiment_workflow_service import ExperimentWorkflowService
from src.controllers.experiment_controller import ExperimentController


class _FakeDeviceManager:
    """Records set_flow calls and reports a configurable per-gas outcome."""

    def __init__(self, failing_gases=()):
        self.failing_gases = set(failing_gases)
        self.calls = []

    def set_flow(self, gas, value):
        self.calls.append((gas, value))
        return gas not in self.failing_gases


class _FakeExperimentApi:
    """Stands in for the facade; forwards to a real controller method."""

    def __init__(self, controller):
        self._controller = controller

    def apply_safety_atmosphere(self):
        return self._controller.apply_safety_atmosphere()


def _controller(device_manager):
    controller = ExperimentController.__new__(ExperimentController)
    controller.device_manager = device_manager
    controller.logger = logging.getLogger("test-controller")
    controller._last_safety_error = ""
    controller.status_updated = _NullSignal()
    controller.system_message_updated = _NullSignal()
    controller.safety_alert = _NullSignal()
    return controller


class _NullSignal:
    def emit(self, *args, **kwargs):
        pass


def _workflow(device_manager):
    controller = _controller(device_manager)
    return ExperimentWorkflowService(
        device_manager=device_manager,
        experiment_api=_FakeExperimentApi(controller),
        experiment_file_manager=None,
        experiment_type_manager=None,
        logger=logging.getLogger("test-workflow"),
    )


# --- 1. the reset button's protective gas -----------------------------------


def test_protective_gas_reports_success_when_every_write_is_confirmed():
    devices = _FakeDeviceManager()
    result = _workflow(devices).apply_protective_gas()

    assert result.success is True
    assert result.message == "已切换到N₂保护气氛"
    assert ("N2", ExperimentController.SAFETY_N2_FLOW_LPM) in devices.calls
    assert ("CO", 0.0) in devices.calls
    assert ("CO2", 0.0) in devices.calls
    assert ("H2", 0.0) in devices.calls


def test_protective_gas_reports_failure_when_a_write_is_not_confirmed():
    devices = _FakeDeviceManager(failing_gases={"H2"})
    result = _workflow(devices).apply_protective_gas()

    assert result.success is False
    assert "H2" in result.message
    assert "已切换到N₂保护气氛" not in result.message


def test_protective_gas_retries_before_declaring_failure():
    devices = _FakeDeviceManager(failing_gases={"CO"})
    _workflow(devices).apply_protective_gas()

    co_attempts = [call for call in devices.calls if call[0] == "CO"]
    assert len(co_attempts) == ExperimentController.SAFETY_FLOW_MAX_ATTEMPTS


def test_protective_gas_requires_a_device_manager():
    workflow = ExperimentWorkflowService(
        device_manager=None,
        experiment_api=None,
        experiment_file_manager=None,
        experiment_type_manager=None,
        logger=logging.getLogger("test-workflow"),
    )
    result = workflow.apply_protective_gas()

    assert result.success is False
    assert "设备管理器未初始化" in result.message


# --- 2. no fail-open when the bus is judged disconnected ---------------------


@pytest.mark.parametrize("is_connected", [True, False])
def test_unconfirmed_stage_flow_is_a_failure_regardless_of_connection_state(is_connected):
    devices = _FakeDeviceManager(failing_gases={"CO"})
    controller = _controller(devices)

    failed = ExperimentController._set_stage_gas_flows(
        controller, {"N2": 10.5, "CO": 4.5}, is_connected
    )

    assert failed == ["CO"], "断线状态不得把未确认的气体设定当作已完成"


def test_confirmed_stage_flows_report_no_failure():
    devices = _FakeDeviceManager()
    controller = _controller(devices)

    assert ExperimentController._set_stage_gas_flows(
        controller, {"N2": 10.5, "CO": 4.5}, True
    ) == []


def test_partial_stage_flow_failure_is_fail_closed():
    devices = _FakeDeviceManager(failing_gases={"H2"})
    controller = _controller(devices)

    failed = ExperimentController._set_stage_gas_flows(
        controller, {"N2": 5.0, "H2": 2.0}, True
    )

    assert failed == ["H2"]
