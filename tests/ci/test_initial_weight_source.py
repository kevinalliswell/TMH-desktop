"""Measured-vs-nominal initial-weight regressions for issue #66."""
import pytest

from tests.ci.test_experiment_flow_threading import _build_controller


def test_parameter_check_uses_nominal_weight_without_measurement(tmp_path, monkeypatch):
    controller, _ = _build_controller(tmp_path, monkeypatch)

    assert controller.check_experiment_params() is True
    assert controller.initial_weight == pytest.approx(523.0)
    assert controller._initial_weight_source == "nominal"


def test_parameter_check_preserves_measured_initial_weight(tmp_path, monkeypatch):
    controller, _ = _build_controller(tmp_path, monkeypatch)
    controller.set_initial_weight(500.123)

    assert controller.check_experiment_params() is True

    assert controller.experiment_params["sample_weight"] == pytest.approx(523.0)
    assert controller.initial_weight == pytest.approx(500.123)
    assert controller._initial_weight_source == "measured"


def test_completed_experiment_does_not_leak_measured_weight_to_next_run(
    tmp_path,
    monkeypatch,
):
    controller, _ = _build_controller(tmp_path, monkeypatch)
    controller.set_initial_weight(500.123)
    assert controller.set_experiment_mode_by_id("GB_13242_2017") is True
    assert controller.start_experiment() is True
    assert controller.stop_experiment() is True

    assert controller.check_experiment_params() is True
    assert controller.initial_weight == pytest.approx(523.0)
    assert controller._initial_weight_source == "nominal"
