from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from src.application.dto import CommunicationConfig
from src.application.ports import DeviceHubPort, SnapshotCollectorPort
from src.application.ports.repository_ports import CommConfigRepositoryPort
from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler
from src.infrastructure.devices import DeviceHubAdapter, SnapshotCollectorAdapter
from src.infrastructure.devices.package_gateways import DevicePackageRegistry
from src.infrastructure.repositories import CommConfigRepository
from src.services.experiment_runtime import ExperimentRuntime
from src.utils.path_manager import PathManager


@dataclass
class RuntimeServices:
    """Backend services assembled by the application runtime."""

    device_manager: DeviceManager
    device_hub: DeviceHubPort
    data_handler: DataHandler
    snapshot_collector: SnapshotCollectorPort
    experiment_runtime: ExperimentRuntime
    communication_config: CommunicationConfig
    device_backend_sources: dict[str, str]
    device_backend_details: dict[str, dict[str, object]]


class AppRuntime(QObject):
    """应用运行时服务，管理设备与数据采集生命周期。"""

    comm_status_updated = Signal(bool, str, str)

    def __init__(
        self,
        parent=None,
        save_interval=60,
        device_manager_factory: Callable[[], DeviceManager] | None = None,
        data_handler_factory: Callable[[str, int], DataHandler] | None = None,
        experiment_runtime_factory: Callable[[DeviceManager, DataHandler, QObject], ExperimentRuntime] | None = None,
        device_registrar: Callable[[DeviceManager], None] | None = None,
        comm_config_repository: CommConfigRepositoryPort | None = None,
        device_package_registry: DevicePackageRegistry | None = None,
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.device_manager = None
        self.device_hub = None
        self.data_handler = None
        self.snapshot_collector = None
        self.experiment_runtime = None
        self.communication_config = None
        self._services = None
        self.comm_status_timer = None
        self.save_interval = save_interval
        self._started = False
        self._device_manager_factory = device_manager_factory or DeviceManager
        self._data_handler_factory = data_handler_factory or self._create_data_handler
        self._experiment_runtime_factory = (
            experiment_runtime_factory or self._create_experiment_runtime
        )
        self._device_registrar = device_registrar or self._register_real_devices
        self._comm_config_repository = comm_config_repository or CommConfigRepository()
        self._device_package_registry = device_package_registry or DevicePackageRegistry()
        self._device_backend_sources = {}
        self._device_backend_details = {}

    def start(self):
        """初始化并启动后端服务。"""
        if self._started:
            return
        db_path = PathManager.get_data_path("device_data.db")
        PathManager.ensure_file_directory_exists(db_path)

        self.communication_config = self._comm_config_repository.load()
        self.device_manager = self._device_manager_factory()
        self.device_hub = DeviceHubAdapter(self.device_manager)
        self.data_handler = self._data_handler_factory(db_path, self.save_interval)
        self.data_handler.set_device_manager(self.device_manager)
        self.data_handler.set_snapshot_provider(self.device_hub)
        self.snapshot_collector = SnapshotCollectorAdapter(self.data_handler)
        self.experiment_runtime = self._experiment_runtime_factory(
            self.device_manager, self.data_handler, self
        )
        self._device_registrar(self.device_manager)
        self._services = RuntimeServices(
            device_manager=self.device_manager,
            device_hub=self.device_hub,
            data_handler=self.data_handler,
            snapshot_collector=self.snapshot_collector,
            experiment_runtime=self.experiment_runtime,
            communication_config=self.communication_config,
            device_backend_sources=dict(self._device_backend_sources),
            device_backend_details=dict(self._device_backend_details),
        )

        self.device_manager.start_all()
        self.data_handler.start()

        self.comm_status_timer = QTimer(self)
        self.comm_status_timer.timeout.connect(self._check_communication_status)
        self.comm_status_timer.start(3000)
        self._started = True

    def stop(self):
        """停止后端服务。"""
        if not self._started:
            return

        # 停止并断开通信状态定时器
        if self.comm_status_timer:
            if self.comm_status_timer.isActive():
                self.comm_status_timer.stop()
            try:
                self.comm_status_timer.timeout.disconnect(self._check_communication_status)
            except (RuntimeError, TypeError):
                pass
            self.comm_status_timer.deleteLater()
            self.comm_status_timer = None

        # 清理实验运行时
        if self.experiment_runtime:
            try:
                self.experiment_runtime.cleanup()
            except Exception as e:
                self.logger.error(f"清理实验运行时出错: {e}")

        # 停止设备管理器
        if self.device_manager:
            try:
                self.device_manager.stop_all()
            except Exception as e:
                self.logger.error(f"关闭设备管理器出错: {e}")

        # 停止数据处理器
        if self.data_handler:
            try:
                self.data_handler.stop()
            except Exception as e:
                self.logger.error(f"关闭数据处理器出错: {e}")

        self.device_manager = None
        self.device_hub = None
        self.data_handler = None
        self.snapshot_collector = None
        self.experiment_runtime = None
        self.communication_config = None
        self._services = None
        self._device_backend_sources = {}
        self._device_backend_details = {}
        self._started = False

    def restart(self):
        """重启后端服务（用于应用新的通信配置）。"""
        self.stop()
        self.start()

    def apply_comm_settings(self):
        """应用通信配置变更。"""
        self.restart()

    @property
    def services(self) -> RuntimeServices:
        """Return assembled runtime services after start()."""
        if self._services is None:
            raise RuntimeError("AppRuntime 尚未启动，无法获取运行时服务")
        return self._services

    @property
    def is_started(self) -> bool:
        """Whether backend services have been started."""
        return self._started

    def _create_data_handler(self, db_path: str, save_interval: int) -> DataHandler:
        return DataHandler(db_path=db_path, save_interval=save_interval)

    def _create_experiment_runtime(
        self,
        device_manager: DeviceManager,
        data_handler: DataHandler,
        parent: QObject,
    ) -> ExperimentRuntime:
        return ExperimentRuntime(device_manager, data_handler, parent)

    def _register_real_devices(self, device_manager: DeviceManager):
        """注册真实设备"""
        build_result = self._device_package_registry.build_devices(self.communication_config)
        self._device_backend_sources = dict(build_result.sources)
        self._device_backend_details = dict(build_result.details)

        for device_name, device in build_result.devices.items():
            try:
                device_manager.register_device(device_name, device)
                self.logger.info(
                    f"{device_name}设备注册成功，来源: {self._device_backend_sources.get(device_name, 'unknown')}"
                )
            except Exception as e:
                self.logger.error(f"{device_name}设备注册失败: {e}")

    def _check_communication_status(self):
        try:
            is_connected, device_names, error_msg = self.device_hub.get_connection_status()
            self.comm_status_updated.emit(is_connected, device_names, error_msg)
        except Exception as e:
            self.logger.error(f"通信状态检查出错: {e}")
            self.comm_status_updated.emit(False, "", str(e))
