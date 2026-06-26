from src.device_clients.device_manager import DeviceManager


class FakeMfcDevice:
    serial_port_available = True

    def __init__(self, latest_data):
        self.latest_data = latest_data

    def is_alive(self):
        return True

    def get_latest_data(self):
        return self.latest_data


def _mfc_status_for(latest_data):
    manager = DeviceManager()
    manager.register_device("MFC", FakeMfcDevice(latest_data))
    return manager.get_connection_status()


def test_mfc_connection_accepts_nested_channel_pv_sv_data():
    is_connected, device_names, error_msg = _mfc_status_for(
        {
            "N2": {"timestamp": 1.0, "PV": 1.23, "SV": 1.50},
            "CO": {"timestamp": 1.0, "PV": None, "SV": None},
        }
    )

    assert is_connected is True
    assert "气体流量计" in device_names
    assert error_msg == ""


def test_mfc_connection_accepts_zero_flow_values():
    is_connected, device_names, error_msg = _mfc_status_for(
        {
            "N2": {"timestamp": 1.0, "PV": 0.0, "SV": 0.0},
            "CO": {"timestamp": 1.0, "PV": None, "SV": None},
        }
    )

    assert is_connected is True
    assert "气体流量计" in device_names
    assert error_msg == ""


def test_mfc_connection_rejects_channels_without_any_pv_sv_data():
    is_connected, device_names, error_msg = _mfc_status_for(
        {
            "N2": {"timestamp": 1.0, "PV": None, "SV": None},
            "CO": {"timestamp": 1.0, "PV": None, "SV": None},
        }
    )

    assert is_connected is False
    assert device_names == ""
    assert "气体流量计" in error_msg


def test_mfc_connection_accepts_single_channel_payload_data():
    is_connected, device_names, error_msg = _mfc_status_for(
        {"timestamp": 1.0, "PV": 1.23, "SV": 1.50}
    )

    assert is_connected is True
    assert "气体流量计" in device_names
    assert error_msg == ""


def test_mfc_connection_accepts_legacy_flat_flow_data():
    is_connected, device_names, error_msg = _mfc_status_for(
        {"N2": 0.0, "CO": None}
    )

    assert is_connected is True
    assert "气体流量计" in device_names
    assert error_msg == ""
