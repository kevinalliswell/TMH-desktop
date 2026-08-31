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
# GB/T 13241 reduction degree includes the FeO baseline and the oxygen bound
# to total iron (0.430 * w(TFe)).
# --------------------------------------------------------------------------
def test_reduction_degree_uses_total_iron_and_feo_contents():
    from src.services.gb13241_calculator import ReductionCalculator

    calc = ReductionCalculator()
    # TFe=60%, FeO=25%, W0=100g and mt=90g:
    # Rt = [0.111*0.25/(0.430*0.60) + 10/(100*0.430*0.60)] * 100
    assert calc.calculate_reduction_degree(100.0, 90.0, 60.0, 25.0) == 49.52


def test_reduction_degree_rejects_invalid_inputs():
    from src.services.gb13241_calculator import ReductionCalculator

    calc = ReductionCalculator()
    assert calc.calculate_reduction_degree(0.0, 0.0, 60.0, 25.0) is None
    assert calc.calculate_reduction_degree(100.0, 85.0, 0.0, 25.0) is None
    assert calc.calculate_reduction_degree(100.0, 85.0, 60.0, -0.1) is None


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
