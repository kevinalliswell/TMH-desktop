"""CI tests for the flammable-gas (H2/CO) flow safety limit.

Covers the hard-clamp logic in MultiMFCClient and round-trip persistence of the
GAS_SAFETY_LIMITS section through CommConfigRepository. No hardware required.
"""
import json

import pytest

from src.device_clients.multi_mfc_client import MultiMFCClient
from src.infrastructure.repositories import CommConfigRepository


def _mfc_config(gas_safety_limits=None):
    config = {
        "COM_RS485_MFC": {
            "port": "COM_TEST",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "E",
            "stopbits": 1,
            "timeout": 0.5,
        },
        "SLAVE_ADDRESS_MFC": {"H2": 1, "N2": 2, "CO2": 3, "CO": 4},
        "FLOW_SCALING": {"H2": 0.1, "N2": 1.0, "CO2": 0.1, "CO": 0.1},
    }
    if gas_safety_limits is not None:
        config["GAS_SAFETY_LIMITS"] = gas_safety_limits
    return config


# --------------------------------------------------------------------------
# Hard-clamp logic (the safety core)
# --------------------------------------------------------------------------
def test_clamp_caps_flammable_gas_above_limit():
    client = MultiMFCClient(_mfc_config({"H2": 5.0, "CO": 5.0}))
    assert client._clamp_flow("H2", 8.0) == 5.0
    assert client._clamp_flow("CO", 12.5) == 5.0


def test_clamp_passes_values_at_or_below_limit():
    client = MultiMFCClient(_mfc_config({"H2": 5.0, "CO": 5.0}))
    assert client._clamp_flow("H2", 5.0) == 5.0
    assert client._clamp_flow("CO", 3.2) == 3.2
    assert client._clamp_flow("H2", 0.0) == 0.0  # safety-atmosphere zero must pass


def test_clamp_ignores_non_flammable_gases():
    client = MultiMFCClient(_mfc_config({"H2": 5.0, "CO": 5.0}))
    # N2/CO2 are not in the limits dict -> never clamped
    assert client._clamp_flow("N2", 100.0) == 100.0
    assert client._clamp_flow("CO2", 50.0) == 50.0


def test_clamp_uses_default_limits_when_section_missing():
    client = MultiMFCClient(_mfc_config(gas_safety_limits=None))
    assert client.gas_safety_limits == {"H2": 5.0, "CO": 5.0}
    assert client._clamp_flow("H2", 9.0) == 5.0


def test_clamp_respects_custom_admin_limit():
    client = MultiMFCClient(_mfc_config({"H2": 3.0, "CO": 8.0}))
    assert client._clamp_flow("H2", 4.0) == 3.0   # stricter admin limit enforced
    assert client._clamp_flow("CO", 7.0) == 7.0   # raised admin limit allows more


# --------------------------------------------------------------------------
# Persistence round-trip through the repository
# --------------------------------------------------------------------------
def test_defaults_include_gas_safety_limits():
    repo = CommConfigRepository(config_file="__does_not_exist__.json")
    assert repo.default_settings["GAS_SAFETY_LIMITS"] == {"H2": 5.0, "CO": 5.0}


def test_missing_section_is_backfilled(tmp_path):
    cfg = tmp_path / "comm_config.json"
    # A config that predates the safety-limit feature (no GAS_SAFETY_LIMITS).
    cfg.write_text(json.dumps({"FLOW_SCALING": {"H2": 0.1, "CO": 0.1}}), encoding="utf-8")
    repo = CommConfigRepository(config_file=str(cfg))
    raw = repo.load_raw()
    assert raw["GAS_SAFETY_LIMITS"] == {"H2": 5.0, "CO": 5.0}


def test_dto_exposes_gas_safety_limits(tmp_path):
    cfg = tmp_path / "comm_config.json"
    repo = CommConfigRepository(config_file=str(cfg))
    config = repo.load()  # creates defaults
    assert config.mfc.gas_safety_limits == {"H2": 5.0, "CO": 5.0}


def test_save_load_round_trip_preserves_limits(tmp_path):
    cfg = tmp_path / "comm_config.json"
    repo = CommConfigRepository(config_file=str(cfg))
    config = repo.load()
    config.mfc.gas_safety_limits["H2"] = 8.0
    config.mfc.gas_safety_limits["CO"] = 2.5
    repo.save(config)

    reloaded = CommConfigRepository(config_file=str(cfg)).load()
    assert reloaded.mfc.gas_safety_limits["H2"] == 8.0
    assert reloaded.mfc.gas_safety_limits["CO"] == 2.5
