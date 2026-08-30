"""Canonical identifiers and metadata for built-in GB experiment modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ExperimentType(Enum):
    """Executable built-in experiment programs."""

    REDUCIBILITY = "GB/T 13241-2017 铁矿石还原性测定方法"
    LOW_TEMP_DEGRADATION = "GB/T 13242-2017 铁矿石低温粉化试验方法"
    FREE_SWELLING = "GB/T 13240-2018 球团矿自由膨胀指数测定方法"


@dataclass(frozen=True)
class StandardModeDefinition:
    mode_id: str
    experiment_type: ExperimentType
    name: str
    description: str
    sample_prefix: str


_STANDARD_MODE_DEFINITIONS = (
    StandardModeDefinition(
        mode_id="GB_13241_2017",
        experiment_type=ExperimentType.REDUCIBILITY,
        name=ExperimentType.REDUCIBILITY.value,
        description="标准铁矿石还原性测定实验",
        sample_prefix="RED",
    ),
    StandardModeDefinition(
        mode_id="GB_13242_2017",
        experiment_type=ExperimentType.LOW_TEMP_DEGRADATION,
        name=ExperimentType.LOW_TEMP_DEGRADATION.value,
        description="低温条件下铁矿石粉化特性测试",
        sample_prefix="RDI",
    ),
    StandardModeDefinition(
        mode_id="GB_13240_2018",
        experiment_type=ExperimentType.FREE_SWELLING,
        name=ExperimentType.FREE_SWELLING.value,
        description="球团矿在还原气氛下的膨胀特性测试",
        sample_prefix="SWE",
    ),
)

STANDARD_MODES: Mapping[str, StandardModeDefinition] = MappingProxyType({
    definition.mode_id: definition
    for definition in _STANDARD_MODE_DEFINITIONS
})
