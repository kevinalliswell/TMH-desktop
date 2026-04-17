from __future__ import annotations

import dataclasses
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum, auto


class ExperimentPhase(Enum):
    """实验生命周期阶段。"""

    IDLE = auto()
    CONFIGURING = auto()
    RUNNING = auto()
    STAGE_TRANSITION = auto()
    COMPLETING = auto()
    STOPPING = auto()
    ERROR = auto()


VALID_TRANSITIONS = {
    ExperimentPhase.IDLE: {ExperimentPhase.CONFIGURING},
    ExperimentPhase.CONFIGURING: {ExperimentPhase.RUNNING, ExperimentPhase.IDLE},
    ExperimentPhase.RUNNING: {
        ExperimentPhase.STAGE_TRANSITION,
        ExperimentPhase.COMPLETING,
        ExperimentPhase.STOPPING,
        ExperimentPhase.ERROR,
    },
    ExperimentPhase.STAGE_TRANSITION: {
        ExperimentPhase.RUNNING,
        ExperimentPhase.COMPLETING,
        ExperimentPhase.STOPPING,
        ExperimentPhase.ERROR,
    },
    ExperimentPhase.COMPLETING: {ExperimentPhase.IDLE},
    ExperimentPhase.STOPPING: {ExperimentPhase.IDLE},
    ExperimentPhase.ERROR: {ExperimentPhase.IDLE},
}


class InvalidTransitionError(Exception):
    """非法状态转换异常。"""

    def __init__(self, from_phase: ExperimentPhase, to_phase: ExperimentPhase):
        self.from_phase = from_phase
        self.to_phase = to_phase
        super().__init__(f"非法状态转换: {from_phase.name} -> {to_phase.name}")


@dataclass
class ExperimentState:
    """实验状态快照（不可变语义的值对象）。"""

    phase: ExperimentPhase = ExperimentPhase.IDLE
    experiment_id: str = ""
    experiment_type_name: str = ""
    initial_weight: float = 0.0
    current_stage_index: int = 0
    total_stages: int = 0
    stage_start_time: float = 0.0
    experiment_start_time: float = 0.0
    elapsed_seconds: int = 0
    error_message: str = ""
    params: dict = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        return self.phase in (
            ExperimentPhase.RUNNING,
            ExperimentPhase.STAGE_TRANSITION,
            ExperimentPhase.COMPLETING,
        )

    @property
    def is_active(self) -> bool:
        return self.phase not in (ExperimentPhase.IDLE, ExperimentPhase.ERROR)


class ExperimentStateMachineCore:
    """纯 Python、线程安全的实验状态机核心。"""

    def __init__(self):
        self._state = ExperimentState()
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

    def get_state(self) -> ExperimentState:
        with self._lock:
            return dataclasses.replace(self._state)

    @property
    def phase(self) -> ExperimentPhase:
        with self._lock:
            return self._state.phase

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._state.is_running

    @property
    def is_idle(self) -> bool:
        with self._lock:
            return self._state.phase == ExperimentPhase.IDLE

    def transition_to(self, new_phase: ExperimentPhase, **updates) -> ExperimentState:
        with self._lock:
            current_phase = self._state.phase
            if not self._is_valid_transition(current_phase, new_phase):
                raise InvalidTransitionError(current_phase, new_phase)

            self._state.phase = new_phase
            self._apply_updates(updates)
            snapshot = dataclasses.replace(self._state)

        self._logger.info(f"状态转换: {current_phase.name} -> {new_phase.name}")
        return snapshot

    def update_state(self, **updates) -> ExperimentState:
        with self._lock:
            self._apply_updates(updates)
            return dataclasses.replace(self._state)

    def update_state_silent(self, **updates) -> ExperimentState:
        return self.update_state(**updates)

    def reset(self) -> ExperimentState:
        with self._lock:
            old_phase = self._state.phase
            self._state = ExperimentState()
            snapshot = dataclasses.replace(self._state)

        self._logger.info(f"状态重置: {old_phase.name} -> IDLE")
        return snapshot

    def _is_valid_transition(self, from_phase: ExperimentPhase, to_phase: ExperimentPhase) -> bool:
        allowed = VALID_TRANSITIONS.get(from_phase, set())
        return to_phase in allowed

    def _apply_updates(self, updates: dict) -> None:
        for key, value in updates.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
            else:
                self._logger.warning(f"尝试更新不存在的状态字段: {key}")
