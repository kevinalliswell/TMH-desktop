# src/models/experiment_state.py
"""
实验状态机模块

提供集中式、线程安全的实验状态管理，作为整个实验生命周期的唯一数据源（Single Source of Truth）。
所有组件（控制器、数据处理器、UI）均从此处查询或变更实验状态。
"""
import dataclasses
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from PySide6.QtCore import QObject, Signal


class ExperimentPhase(Enum):
    """实验生命周期阶段"""
    IDLE = auto()               # 空闲，无实验运行
    CONFIGURING = auto()        # 正在配置实验参数
    RUNNING = auto()            # 实验运行中
    STAGE_TRANSITION = auto()   # 阶段切换中
    COMPLETING = auto()         # 实验正在完成（自动完成流程）
    STOPPING = auto()           # 用户手动停止中
    ERROR = auto()              # 发生错误


# 合法的状态转换映射
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
    """非法状态转换异常"""
    def __init__(self, from_phase: ExperimentPhase, to_phase: ExperimentPhase):
        self.from_phase = from_phase
        self.to_phase = to_phase
        super().__init__(
            f"非法状态转换: {from_phase.name} -> {to_phase.name}"
        )


@dataclass
class ExperimentState:
    """
    实验状态快照（不可变值对象）

    每次状态变更后，通过 dataclasses.replace() 生成新的快照，
    确保外部持有的快照不会被后续变更覆盖。
    """
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
        """实验是否处于活跃运行状态"""
        return self.phase in (
            ExperimentPhase.RUNNING,
            ExperimentPhase.STAGE_TRANSITION,
            ExperimentPhase.COMPLETING,
        )

    @property
    def is_active(self) -> bool:
        """实验是否处于活跃状态（包含配置和停止中）"""
        return self.phase not in (ExperimentPhase.IDLE, ExperimentPhase.ERROR)


class ExperimentStateMachine(QObject):
    """
    集中式实验状态机

    - 线程安全：所有读写通过 RLock 保护
    - 转换验证：只允许 VALID_TRANSITIONS 中定义的合法转换
    - 信号驱动：每次状态变更后发射 state_changed 信号（携带快照）
    - 可选更新：transition_to / update_state 支持同时更新字段值
    """
    state_changed = Signal(object)  # 发射 ExperimentState 快照

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = ExperimentState()
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

    # ── 查询接口 ────────────────────────────────────────

    def get_state(self) -> ExperimentState:
        """返回当前状态的不可变快照（线程安全）"""
        with self._lock:
            return dataclasses.replace(self._state)

    @property
    def phase(self) -> ExperimentPhase:
        """当前阶段（便捷属性）"""
        with self._lock:
            return self._state.phase

    @property
    def is_running(self) -> bool:
        """实验是否运行中（便捷属性）"""
        with self._lock:
            return self._state.is_running

    @property
    def is_idle(self) -> bool:
        """实验是否空闲（便捷属性）"""
        with self._lock:
            return self._state.phase == ExperimentPhase.IDLE

    # ── 状态转换接口 ────────────────────────────────────

    def transition_to(
        self, new_phase: ExperimentPhase, **updates
    ) -> ExperimentState:
        """
        执行一次合法的状态转换，同时可更新字段。

        Args:
            new_phase: 目标阶段
            **updates: 需要同时更新的字段（如 experiment_id, initial_weight 等）

        Returns:
            ExperimentState: 转换后的状态快照

        Raises:
            InvalidTransitionError: 如果转换不合法
        """
        with self._lock:
            current_phase = self._state.phase
            if not self._is_valid_transition(current_phase, new_phase):
                raise InvalidTransitionError(current_phase, new_phase)

            self._state.phase = new_phase
            self._apply_updates(updates)
            snapshot = dataclasses.replace(self._state)

        self._logger.info(
            f"状态转换: {current_phase.name} -> {new_phase.name}"
        )
        self.state_changed.emit(snapshot)
        return snapshot

    def update_state(self, **updates) -> ExperimentState:
        """
        在当前阶段内更新字段值（不改变阶段）。

        用于定时器更新 elapsed_seconds、stage_start_time 等场景。

        Args:
            **updates: 需要更新的字段

        Returns:
            ExperimentState: 更新后的状态快照
        """
        with self._lock:
            self._apply_updates(updates)
            snapshot = dataclasses.replace(self._state)

        self.state_changed.emit(snapshot)
        return snapshot

    def update_state_silent(self, **updates) -> ExperimentState:
        """
        静默更新字段（不发射信号）。

        用于高频更新场景（如每秒更新 elapsed_seconds），
        避免信号风暴。调用方在需要时手动发射信号。

        Args:
            **updates: 需要更新的字段

        Returns:
            ExperimentState: 更新后的状态快照
        """
        with self._lock:
            self._apply_updates(updates)
            return dataclasses.replace(self._state)

    def reset(self) -> ExperimentState:
        """重置到 IDLE 状态，清空所有字段"""
        with self._lock:
            old_phase = self._state.phase
            self._state = ExperimentState()
            snapshot = dataclasses.replace(self._state)

        self._logger.info(f"状态重置: {old_phase.name} -> IDLE")
        self.state_changed.emit(snapshot)
        return snapshot

    # ── 内部方法 ────────────────────────────────────────

    def _is_valid_transition(
        self, from_phase: ExperimentPhase, to_phase: ExperimentPhase
    ) -> bool:
        """检查状态转换是否合法"""
        allowed = VALID_TRANSITIONS.get(from_phase, set())
        return to_phase in allowed

    def _apply_updates(self, updates: dict) -> None:
        """将键值对应用到内部状态（需在锁内调用）"""
        for key, value in updates.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
            else:
                self._logger.warning(
                    f"尝试更新不存在的状态字段: {key}"
                )
