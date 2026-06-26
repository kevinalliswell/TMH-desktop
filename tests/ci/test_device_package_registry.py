from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject

from src.application.dto import (
    BalanceCommunicationConfig,
    CommunicationConfig,
    DeviceSnapshot,
    HealthStatus,
    MfcCommunicationConfig,
    PerformanceConfig,
    SamplingConfig,
    SerialPortConfig,
    TemperatureCommunicationConfig,
)
from src.infrastructure.devices.package_gateways import DeviceBuildResult, DevicePackageRegistry
from src.infrastructure.devices.package_gateways import device_package_registry as registry_module
from src.services.app_runtime import AppRuntime


def _build_config() -> CommunicationConfig:
    return CommunicationConfig(
        mfc=MfcCommunicationConfig(
            serial=SerialPortConfig(
                port="COM-MFC",
                baudrate=9600,
                bytesize=8,
                parity="E",
                stopbits=1,
                timeout=0.5,
            ),
            slave_addresses={"N2": 2, "CO": 4},
            flow_scaling={"N2": 1.0, "CO": 0.1},
        ),
        temperature=TemperatureCommunicationConfig(
            serial=SerialPortConfig(
                port="COM-TEMP",
                baudrate=9600,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=1.0,
            ),
            slave_address=3,
            start_reg=10,
            reg_count=9,
            temp_channels=["T1", "T2", "T3"],
            scale=0.1,
            signed_registers=False,
        ),
        balance=BalanceCommunicationConfig(
            serial=SerialPortConfig(
                port="COM-BAL",
                baudrate=1200,
                bytesize=8,
                parity="E",
                stopbits=1,
                timeout=1.0,
            )
        ),
        sampling=SamplingConfig(interval_s=1.0),
        performance=PerformanceConfig(
            data_collection_interval=0.2,
            experiment_data_interval=1.0,
            heartbeat_timeout=5.0,
        ),
    )


def test_registry_builds_external_adapters_when_packages_are_available(monkeypatch):
    config = _build_config()

    @dataclass
    class _Config:
        port: str
        baudrate: int
        bytesize: int
        parity: str
        stopbits: int
        timeout: float
        read_interval: float | None = None
        slave_address: int | None = None
        start_reg: int | None = None
        reg_count: int | None = None
        scale: float | None = None
        signed_registers: bool | None = None
        temp_channels: list[str] | None = None
        poll_interval: float | None = None
        slave_addresses: dict[str, int] | None = None
        flow_scaling: dict[str, float] | None = None

    class FakeBalancePackage:
        def __init__(self, config):
            self.config = config
            self.model = "PkgBalance"
            self.started = False
            self.tare_called = False

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def health(self):
            return HealthStatus(is_connected=True, is_running=self.started, last_update_ts=123.0)

        def read_snapshot(self):
            return DeviceSnapshot(
                device_name="Balance",
                device_type="weight",
                timestamp=123.0,
                payload={"weight": 12.34},
                is_connected=True,
                is_running=self.started,
            )

        def tare(self):
            self.tare_called = True
            return True

    class FakeTempPackage:
        def __init__(self, config):
            self.config = config
            self.model = "PkgTemp"
            self.started = False

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def health(self):
            return HealthStatus(is_connected=True, is_running=self.started, last_update_ts=456.0)

        def read_snapshot(self):
            return DeviceSnapshot(
                device_name="Temp",
                device_type="temperature",
                timestamp=456.0,
                payload={"T1": 100.1, "T2": 101.2},
                is_connected=True,
                is_running=self.started,
            )

    class FakeMfcPackage:
        def __init__(self, config):
            self.config = config
            self.model = "PkgMFC"
            self.started = False
            self.last_set_flow = None

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def health(self):
            return HealthStatus(is_connected=True, is_running=self.started, last_update_ts=789.0)

        def get_latest_data(self, gas_name=None):
            data = {
                "N2": {"timestamp": 789.0, "pv": 1.2, "sv": 1.5},
                "CO": {"timestamp": 789.0, "pv": 0.4, "sv": 0.5},
            }
            if gas_name is None:
                return data
            return data.get(gas_name)

        def set_flow(self, gas_name, flow_value):
            self.last_set_flow = (gas_name, flow_value)
            return True

    def fake_import(module_name):
        if module_name == "tmh_device_balance":
            return type(
                "FakeBalanceModule",
                (),
                {"BalanceDeviceConfig": _Config, "BalanceClient": FakeBalancePackage},
            )
        if module_name == "tmh_device_temp":
            return type(
                "FakeTempModule",
                (),
                {"TempDeviceConfig": _Config, "TempControllerClient": FakeTempPackage},
            )
        if module_name == "tmh_device_mfc":
            return type(
                "FakeMfcModule",
                (),
                {"MfcDeviceConfig": _Config, "MfcDevice": FakeMfcPackage},
            )
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(registry_module, "import_module", fake_import)

    registry = DevicePackageRegistry()
    result = registry.build_devices(config)

    assert result.sources == {
        "Balance": "external-package",
        "Temp": "external-package",
        "MFC": "external-package",
    }
    assert result.details["Balance"]["module"] == "FakeBalanceModule"
    assert result.details["MFC"]["class_name"] == "MfcDevice"

    balance = result.devices["Balance"]
    temp = result.devices["Temp"]
    mfc = result.devices["MFC"]

    balance.start()
    temp.start()
    mfc.start()

    assert balance.serial_port_available is True
    assert balance.get_data()["weight"] == 12.34
    assert balance.send_tare_command() is True
    assert balance.device.tare_called is True
    assert balance.device.config.port == "COM-BAL"

    assert temp.serial_port_available is True
    assert temp.get_data()["T1"] == 100.1
    assert temp.device.config.slave_address == 3

    assert mfc.current_flows["N2"] == 1.2
    assert mfc.setpoints["CO"] == 0.5
    assert mfc.set_sp_value("N2", 5.0) is True
    assert mfc.device.last_set_flow == ("N2", 5.0)
    assert mfc.device.config.slave_addresses == {"N2": 2, "CO": 4}


def test_registry_falls_back_to_legacy_builders_when_packages_are_missing(monkeypatch):
    config = _build_config()

    class LegacyRegistry(DevicePackageRegistry):
        def _build_legacy_balance(self, config):
            return {"kind": "balance-legacy", "port": config.balance.serial.port}

        def _build_legacy_temp(self, config):
            return {"kind": "temp-legacy", "port": config.temperature.serial.port}

        def _build_legacy_mfc(self, config):
            return {"kind": "mfc-legacy", "port": config.mfc.serial.port}

    monkeypatch.setattr(
        registry_module,
        "import_module",
        lambda module_name: (_ for _ in ()).throw(ModuleNotFoundError(module_name)),
    )

    registry = LegacyRegistry()
    result = registry.build_devices(config)

    assert result.sources == {
        "Balance": "legacy-local",
        "Temp": "legacy-local",
        "MFC": "legacy-local",
    }
    assert result.devices["Balance"]["kind"] == "balance-legacy"
    assert result.devices["Temp"]["port"] == "COM-TEMP"
    assert result.devices["MFC"]["port"] == "COM-MFC"
    assert result.details["Balance"]["backend"] == "legacy-local"
    assert result.details["Balance"]["class_name"] == "dict"


def test_registry_supports_env_module_alias_and_import_path(monkeypatch, tmp_path):
    config = _build_config()
    module_dir = tmp_path / "dev_balance_pkg"
    module_dir.mkdir()
    (module_dir / "dev_balance_module.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class BalanceDeviceConfig:\n"
        "    port: str\n"
        "    baudrate: int\n"
        "    bytesize: int\n"
        "    parity: str\n"
        "    stopbits: int\n"
        "    timeout: float\n"
        "    read_interval: float | None = None\n"
        "class BalanceClient:\n"
        "    def __init__(self, config):\n"
        "        self.config = config\n"
        "        self.model = 'DevBalance'\n"
        "        self.started = False\n"
        "    def start(self):\n"
        "        self.started = True\n"
        "    def stop(self):\n"
        "        self.started = False\n"
        "    def health(self):\n"
        "        from src.application.dto import HealthStatus\n"
        "        return HealthStatus(is_connected=True, is_running=self.started, last_update_ts=42.0)\n"
        "    def read_snapshot(self):\n"
        "        from src.application.dto import DeviceSnapshot\n"
        "        return DeviceSnapshot(device_name='Balance', device_type='weight', timestamp=42.0, payload={'weight': 9.87})\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("TMH_DEVICE_BALANCE_MODULE", "dev_balance_module")
    monkeypatch.setenv("TMH_DEVICE_BALANCE_PATH", str(module_dir))

    registry = DevicePackageRegistry()
    balance = registry.build_devices(config).devices["Balance"]

    assert balance.get_data()["weight"] == 9.87
    assert balance.device.config.port == "COM-BAL"


def test_app_runtime_assembles_devices_from_registry_and_repository(tmp_path):
    app = QCoreApplication.instance() or QCoreApplication([])
    config = _build_config()
    stop_order = []

    class FakeDevice:
        def __init__(self, name):
            self.name = name
            self.started = False
            self.stopped = False

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def is_alive(self):
            return self.started and not self.stopped

        def get_data(self):
            return {"timestamp": 1.0}

    class FakeDeviceManager:
        def __init__(self):
            self.devices = {}
            self.running = False

        def register_device(self, name, device):
            self.devices[name] = device

        def start_all(self):
            self.running = True
            for device in self.devices.values():
                device.start()

        def stop_all(self):
            stop_order.append("devices")
            self.running = False
            for device in self.devices.values():
                device.stop()
            self.devices = {}

        def get_connection_status(self):
            return True, "Balance, Temp, MFC", ""

        def get_status_legacy(self):
            return {"frames": {}, "timestamp": 1.0}

        def get_status(self, name=None):
            return self.get_status_legacy()

    class FakeDataHandler:
        def __init__(self, db_path, save_interval):
            self.db_path = db_path
            self.save_interval = save_interval
            self.device_manager = None
            self.snapshot_provider = None
            self.started = False
            self.stopped = False

        def set_device_manager(self, device_manager):
            self.device_manager = device_manager

        def set_snapshot_provider(self, snapshot_provider):
            self.snapshot_provider = snapshot_provider

        def start(self):
            self.started = True

        def stop(self):
            stop_order.append("data_handler")
            self.stopped = True

        def latest_snapshot_bundle(self):
            return None

    class FakeExperimentRuntime:
        def __init__(self, device_manager, data_handler, parent):
            self.device_manager = device_manager
            self.data_handler = data_handler
            self.parent = parent
            self.cleaned = False

        def cleanup(self):
            stop_order.append("experiment_runtime")
            self.cleaned = True

    class FakeRepository:
        def load(self):
            return config

    class FakeRegistry:
        def build_devices(self, loaded_config):
            assert loaded_config is config
            return DeviceBuildResult(
                devices={
                    "Balance": FakeDevice("Balance"),
                    "Temp": FakeDevice("Temp"),
                    "MFC": FakeDevice("MFC"),
                },
                sources={
                    "Balance": "external-package",
                    "Temp": "external-package",
                    "MFC": "external-package",
                },
                details={
                    "Balance": {"backend": "external-package", "module": "fake.balance"},
                    "Temp": {"backend": "external-package", "module": "fake.temp"},
                    "MFC": {"backend": "external-package", "module": "fake.mfc"},
                },
            )

    runtime_parent = QObject()
    runtime = AppRuntime(
        parent=runtime_parent,
        device_manager_factory=FakeDeviceManager,
        data_handler_factory=lambda db_path, save_interval: FakeDataHandler(db_path, save_interval),
        experiment_runtime_factory=lambda device_manager, data_handler, parent: FakeExperimentRuntime(
            device_manager, data_handler, parent
        ),
        comm_config_repository=FakeRepository(),
        device_package_registry=FakeRegistry(),
    )

    runtime.start()

    assert runtime.services.communication_config is config
    assert runtime._device_backend_sources["Balance"] == "external-package"
    assert runtime.services.device_backend_sources["MFC"] == "external-package"
    assert runtime.services.device_backend_details["Temp"]["module"] == "fake.temp"
    assert sorted(runtime.device_manager.devices.keys()) == ["Balance", "MFC", "Temp"]
    assert runtime.data_handler.started is True
    assert all(device.started for device in runtime.device_manager.devices.values())

    data_handler = runtime.data_handler
    experiment_runtime = runtime.experiment_runtime
    runtime.stop()

    assert data_handler.stopped is True
    assert experiment_runtime.cleaned is True
    assert stop_order == ["experiment_runtime", "data_handler", "devices"]
    assert runtime.experiment_runtime is None
    assert runtime.device_manager is None
    assert app is not None
    assert runtime_parent is not None
