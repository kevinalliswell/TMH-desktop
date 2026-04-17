from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from src.domain.experiment import (
    ExperimentPhase,
    ExperimentStateMachineCore,
    InvalidTransitionError,
)
from src.models.experiment_state import ExperimentStateMachine


def test_domain_state_machine_core_supports_transition_and_silent_update():
    core = ExperimentStateMachineCore()

    snapshot = core.transition_to(
        ExperimentPhase.CONFIGURING,
        experiment_id="exp-001",
        initial_weight=123.4,
    )
    assert snapshot.phase == ExperimentPhase.CONFIGURING
    assert snapshot.experiment_id == "exp-001"
    assert snapshot.initial_weight == 123.4

    updated = core.update_state_silent(elapsed_seconds=10, current_stage_index=2)
    assert updated.elapsed_seconds == 10
    assert updated.current_stage_index == 2
    assert core.get_state().elapsed_seconds == 10


def test_domain_state_machine_core_rejects_invalid_transition():
    core = ExperimentStateMachineCore()

    try:
        core.transition_to(ExperimentPhase.RUNNING)
    except InvalidTransitionError as exc:
        assert exc.from_phase == ExperimentPhase.IDLE
        assert exc.to_phase == ExperimentPhase.RUNNING
    else:
        raise AssertionError("Expected InvalidTransitionError")


def test_qt_state_machine_wrapper_emits_state_changed_signal():
    app = QCoreApplication.instance() or QCoreApplication([])
    emitted = []
    machine = ExperimentStateMachine()
    machine.state_changed.connect(lambda state: emitted.append(state))

    machine.transition_to(ExperimentPhase.CONFIGURING, experiment_id="exp-002")
    machine.update_state(total_stages=3)
    machine.update_state_silent(elapsed_seconds=5)

    assert len(emitted) == 2
    assert emitted[0].phase == ExperimentPhase.CONFIGURING
    assert emitted[0].experiment_id == "exp-002"
    assert emitted[1].total_stages == 3
    assert machine.get_state().elapsed_seconds == 5
    assert app is not None
