"""Safety net for GB experiment stage logic (review issues #64, #57 item 3).

See test_review_safety_net_protocols.py for the safety-net test conventions
(baseline / KNOWN_BUG / strict-xfail).
"""
import pytest

from src.services.enhanced_experiment_modes import (
    CustomExperimentProgram,
    EnhancedExperimentModeManager,
)
from src.services.experiment_modes import (
    ExperimentModeManager,
    ExperimentStage,
    ExperimentType,
    GasSettings,
    StageSettings,
)

ALL_STANDARD_TYPES = [
    ExperimentType.REDUCIBILITY,
    ExperimentType.LOW_TEMP_DEGRADATION,
    ExperimentType.FREE_SWELLING,
]


def _manager_at_stage(experiment_type: ExperimentType, stage: ExperimentStage) -> ExperimentModeManager:
    mgr = ExperimentModeManager()
    assert mgr.set_experiment_mode(experiment_type)
    stages = mgr.get_experiment_stages(experiment_type)
    mgr.current_stage_index = next(i for i, s in enumerate(stages) if s.stage is stage)
    mgr.current_stage = stage
    return mgr


def test_every_standard_program_has_four_stages_baseline():
    mgr = ExperimentModeManager()
    for etype in ALL_STANDARD_TYPES:
        stages = [s.stage for s in mgr.get_experiment_stages(etype)]
        assert stages == [
            ExperimentStage.HEATING,
            ExperimentStage.STABILIZING,
            ExperimentStage.REDUCING,
            ExperimentStage.COOLING,
        ], etype.name


def test_reducing_stage_advancement_baseline():
    mgr = _manager_at_stage(ExperimentType.REDUCIBILITY, ExperimentStage.REDUCING)
    assert mgr.can_advance_stage(900.0, 180 * 60) is True  # on target, time served
    assert mgr.can_advance_stage(900.0, 60 * 60) is False  # too early
    assert mgr.can_advance_stage(880.0, 180 * 60) is False  # out of tolerance


@pytest.mark.parametrize(
    "etype,near_target",
    [
        (ExperimentType.REDUCIBILITY, 25.3),
        (ExperimentType.LOW_TEMP_DEGRADATION, 25.3),
        (ExperimentType.FREE_SWELLING, 50.4),
    ],
)
def test_cooling_stage_completes_near_target(etype, near_target):
    mgr = _manager_at_stage(etype, ExperimentStage.COOLING)
    assert mgr.can_advance_stage(near_target, 3600.0) is True


def test_cooling_stages_have_positive_tolerance():
    mgr = ExperimentModeManager()
    for etype in ALL_STANDARD_TYPES:
        cooling = [s for s in mgr.get_experiment_stages(etype) if s.stage is ExperimentStage.COOLING]
        assert cooling and all(s.temp_tolerance > 0 for s in cooling), etype.name


def test_cooling_stage_uses_an_upper_temperature_threshold():
    mgr = _manager_at_stage(ExperimentType.REDUCIBILITY, ExperimentStage.COOLING)

    assert mgr.can_advance_stage(20.0, 3600.0) is True
    assert mgr.can_advance_stage(30.1, 3600.0) is False


@pytest.mark.xfail(
    strict=True,
    reason="#57 item 3: to_dict writes stage.value ('升温') but the parser maps only enum names, degrading every stage to IDLE",
)
def test_custom_stage_serialization_round_trip_expected():
    stage = StageSettings(
        stage=ExperimentStage.HEATING,
        gas_settings=GasSettings(N2=5.0, total_flow=5.0),
        target_temp=500.0,
        temp_tolerance=5.0,
        duration=10.0,
        heating_rate=10.0,
        description="round-trip",
    )
    program = CustomExperimentProgram(type_id="rt", name="rt", description="", stages=[stage])
    mgr = EnhancedExperimentModeManager()
    parsed = mgr._parse_custom_stages(program.to_dict()["stages"])
    assert [s.stage for s in parsed] == [ExperimentStage.HEATING]
