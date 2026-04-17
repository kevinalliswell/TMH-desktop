from __future__ import annotations

from typing import Any, Protocol

from src.application.dto.communication_dto import CommunicationConfig


class ExperimentRepositoryPort(Protocol):
    """Persistence contract for experiment lifecycle data."""

    def create_experiment(self, payload: dict[str, Any]) -> str:
        ...

    def append_data_point(self, experiment_id: str, payload: dict[str, Any]) -> None:
        ...

    def finish_experiment(self, experiment_id: str, payload: dict[str, Any]) -> None:
        ...


class CommConfigRepositoryPort(Protocol):
    """Persistence contract for communication settings."""

    def load(self) -> CommunicationConfig:
        ...

    def save(self, config: CommunicationConfig) -> None:
        ...


class ExperimentModeRepositoryPort(Protocol):
    """Persistence contract for experiment mode definitions."""

    def load_modes(self) -> dict[str, Any]:
        ...

    def save_modes(self, modes: dict[str, Any]) -> None:
        ...

