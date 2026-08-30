"""Regression tests for bugs found during the code review.

Each test pins a specific defect that was fixed so it cannot silently regress.
All tests are hardware-free and run headless in CI.
"""
from __future__ import annotations

import pytest

from tmh_comm.protocols.mfc_cpl import MfcCplProtocol, _cpl_checksum


def _cpl_frame(body: str) -> bytes:
    framed = f"\x02{body}\x03"
    return f"{framed}{_cpl_checksum(framed)}\r\n".encode()


# --------------------------------------------------------------------------
# GB/T 13241 reduction degree: oxygen content is a percentage, not a fraction.
# Previously the formula used it directly, yielding a result 100x too small.
# --------------------------------------------------------------------------
def test_reduction_degree_treats_oxygen_content_as_percentage():
    from src.services.gb13241_calculator import ReductionCalculator

    calc = ReductionCalculator()
    # W0=100g, current=85g -> weight loss 15g; O2 = 30% -> removable oxygen 30g.
    # Rt = 15 / (100 * 0.30) * 100 = 50%
    assert calc.calculate_reduction_degree(100.0, 85.0, 30.0) == 50.0


def test_reduction_degree_rejects_invalid_inputs():
    from src.services.gb13241_calculator import ReductionCalculator

    calc = ReductionCalculator()
    assert calc.calculate_reduction_degree(0.0, 0.0, 30.0) is None
    assert calc.calculate_reduction_degree(100.0, 85.0, 0.0) is None


# --------------------------------------------------------------------------
# MFC CPL response parsing must handle real device frames that end in
# <ETX><checksum>\r\n, not only the trimmed mock used by the old test.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "frame, slave, expected",
    [
        (_cpl_frame("0100X20,30"), 1, 3.0),
        (_cpl_frame("0500X00,52"), 5, 5.2),
        (b"", 1, None),
        (b"Invalid data", 1, None),
    ],
)
def test_cpl_parse_response_handles_real_frames(frame, slave, expected):
    assert MfcCplProtocol().parse_response(frame, expected_slave=slave) == expected


# --------------------------------------------------------------------------
# experiment_data dataclasses must be importable (previously a non-default
# field followed a defaulted base field, raising TypeError at import time).
# --------------------------------------------------------------------------
def test_experiment_data_module_imports_and_constructs():
    from datetime import datetime

    from src.services import experiment_data as ed

    r = ed.ReductionExperimentData(
        experiment_id="e1",
        experiment_name="n",
        sample_name="s",
        start_time=datetime(2026, 1, 1),
        operator="op",
    )
    assert r.initial_sample_weight_g == 0.0
    assert r.oxygen_content_percentage == 0.0
    assert ed.RDIExperimentData is not None
    assert ed.SwellingExperimentData is not None


# --------------------------------------------------------------------------
# Switching from a custom experiment mode back to a standard mode must clear
# the stale custom-type flag, otherwise the standard program is ignored.
# --------------------------------------------------------------------------
def test_set_experiment_mode_clears_stale_custom_type():
    from src.services.enhanced_experiment_modes import (
        EnhancedExperimentModeManager,
        ExperimentType,
    )

    mgr = EnhancedExperimentModeManager()
    mgr._current_custom_type = "some_custom_type"
    assert mgr.set_experiment_mode(ExperimentType.REDUCIBILITY) is True
    assert mgr._current_custom_type is None
