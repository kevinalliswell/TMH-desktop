from __future__ import annotations

from types import SimpleNamespace

from src.ui.presenters.experiment_control_presenter import ExperimentControlPresenter


class _RaceView:
    def __init__(self):
        self.errors: list[tuple[str, str]] = []

    def confirm(self, *_args, **_kwargs):
        return True

    def has_exportable_data(self):
        return False

    def show_error(self, title, message):
        self.errors.append((title, message))


class _CompletingApi:
    def __init__(self):
        self.checks = 0

    def is_experiment_running(self):
        self.checks += 1
        return self.checks == 1


def test_natural_completion_during_stop_confirmation_is_not_reported_as_error():
    view = _RaceView()
    api = _CompletingApi()
    workflow = SimpleNamespace(
        stop_experiment=lambda: SimpleNamespace(
            success=False,
            message="没有正在运行的实验",
        )
    )
    logger = SimpleNamespace(info=lambda *_args: None, error=lambda *_args: None)
    presenter = ExperimentControlPresenter(view, api, workflow, logger)

    presenter.handle_stop_experiment()

    assert api.checks == 2
    assert view.errors == []
