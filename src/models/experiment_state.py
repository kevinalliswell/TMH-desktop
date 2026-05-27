# src/models/experiment_state.py
"""
实验状态机 Qt 适配模块。

领域核心已迁移到 `src.domain.experiment.state_machine`。
本文件保留 Qt Signal 兼容壳，避免上层 UI / Runtime / Controller
 在 PR-9 中发生大面积接口变更。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from src.domain.experiment.state_machine import (
    ExperimentPhase,
    ExperimentState,
    ExperimentStateMachineCore,
    InvalidTransitionError,
    VALID_TRANSITIONS,
)


class ExperimentStateMachine(QObject):
    """
    Qt 兼容状态机壳。

    - 内部委托纯 Python 的 `ExperimentStateMachineCore`
    - 保留 `state_changed` 信号，兼容现有 UI / Runtime 订阅方式
    """

    state_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._core = ExperimentStateMachineCore()

    @property
    def core(self) -> ExperimentStateMachineCore:
        """Expose the pure domain state machine for non-Qt consumers."""
        return self._core

    def get_state(self) -> ExperimentState:
        return self._core.get_state()

    @property
    def phase(self) -> ExperimentPhase:
        return self._core.phase

    @property
    def is_running(self) -> bool:
        return self._core.is_running

    @property
    def is_idle(self) -> bool:
        return self._core.is_idle

    def transition_to(self, new_phase: ExperimentPhase, **updates) -> ExperimentState:
        snapshot = self._core.transition_to(new_phase, **updates)
        self.state_changed.emit(snapshot)
        return snapshot

    def update_state(self, **updates) -> ExperimentState:
        snapshot = self._core.update_state(**updates)
        self.state_changed.emit(snapshot)
        return snapshot

    def update_state_silent(self, **updates) -> ExperimentState:
        return self._core.update_state_silent(**updates)

    def reset(self) -> ExperimentState:
        snapshot = self._core.reset()
        self.state_changed.emit(snapshot)
        return snapshot


__all__ = [
    "ExperimentPhase",
    "ExperimentState",
    "ExperimentStateMachine",
    "ExperimentStateMachineCore",
    "InvalidTransitionError",
    "VALID_TRANSITIONS",
]
