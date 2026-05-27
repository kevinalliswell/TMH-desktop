from __future__ import annotations

from typing import Protocol


class UserInteractionPort(Protocol):
    """UI interaction contract consumed by application services."""

    def confirm(self, title: str, message: str, default_no: bool = False) -> bool:
        ...

    def input_float(
        self,
        title: str,
        label: str,
        value: float,
        min_value: float,
        max_value: float,
        decimals: int,
    ) -> tuple[float, bool]:
        ...

    def show_info(self, title: str, message: str) -> None:
        ...

    def show_error(self, title: str, message: str) -> None:
        ...
