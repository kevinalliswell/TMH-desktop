"""Contract guard for the experiment-start pass-through chain.

ExperimentWorkflowService.start_experiment calls
``experiment_api.start_experiment(experiment_record)``. The production
``experiment_api`` is an ``ExperimentFacade`` wrapping an ``ExperimentRuntime``;
both pass-throughs MUST accept and forward that optional argument down to the
controller. A prior change updated only ``ExperimentController`` and left the
facade/runtime taking no argument, so every real UI start raised ``TypeError`` —
CI missed it because the lifecycle test injected a stub whose signature happened
to match. These tests exercise the REAL shipped objects.
"""
import inspect

from src.services.experiment_facade import ExperimentFacade
from src.services.experiment_runtime import ExperimentRuntime


def test_pass_through_signatures_accept_experiment_record():
    for cls in (ExperimentFacade, ExperimentRuntime):
        params = list(inspect.signature(cls.start_experiment).parameters)
        assert len(params) >= 2, (
            f"{cls.__name__}.start_experiment must accept an experiment_record "
            f"argument (workflow_service passes it); got {params}"
        )


class _RecordingRuntime:
    """Minimal stand-in for ExperimentRuntime that records the forwarded record."""

    def __init__(self):
        self.received = "UNSET"

    def start_experiment(self, experiment_record=None):
        self.received = experiment_record
        return True


def test_facade_forwards_experiment_record_to_runtime():
    runtime = _RecordingRuntime()
    facade = ExperimentFacade(runtime)
    sentinel = object()

    assert facade.start_experiment(sentinel) is True
    assert runtime.received is sentinel

    # The no-arg call (other call sites) must still work and forward None.
    runtime.received = "UNSET"
    assert facade.start_experiment() is True
    assert runtime.received is None
