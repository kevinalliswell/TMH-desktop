from __future__ import annotations

import pytest

from tmh_comm.protocols.balance_rs232 import BalanceRs232Protocol


def test_tare_response_accepts_a00_ack() -> None:
    result = BalanceRs232Protocol().parse_tare_response("A00\r\n")

    assert result.success is True
    assert result.a00_found is True
    assert result.stable_data_found is False
    assert result.weight is None


@pytest.mark.parametrize("line, weight", [("+00000.0 G S", 0.0), ("-00000.1 G S", -0.1)])
def test_tare_response_accepts_stable_zero_weight_without_ack(line: str, weight: float) -> None:
    result = BalanceRs232Protocol().parse_tare_response(line)

    assert result.success is True
    assert result.a00_found is False
    assert result.stable_data_found is True
    assert result.weight == pytest.approx(weight)


def test_tare_response_rejects_nonzero_stable_weight_without_ack() -> None:
    result = BalanceRs232Protocol().parse_tare_response("+00017.3 G S")

    assert result.success is False
    assert result.a00_found is False
    assert result.stable_data_found is True
    assert result.weight == pytest.approx(17.3)
