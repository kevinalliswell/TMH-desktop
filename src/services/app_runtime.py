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
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager
from src.utils.path_manager import PathManager


@dataclass
class RuntimeServices:
    """Backend services assembled by the application runtime."""

    device_manager: DeviceManager
    device_hub: DeviceHubPort
    data_handler: DataHandler
    snapshot_collector: SnapshotCollectorPort
    experiment_runtime: ExperimentRuntime
    experiment_mode_manager: EnhancedExperimentModeManager
    experiment_type_manager: ExperimentTypeManager
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
        experiment_mode_manager: EnhancedExperimentModeManager | None = None,
        experiment_type_manager: ExperimentTypeManager | None = None,
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
        # 上一次 stop() 是否确认所有设备线程都已退出并释放串口。
        self._devices_released = True
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
        self.experiment_mode_manager = (
            experiment_mode_manager or EnhancedExperimentModeManager()
        )
        self.experiment_type_manager = (
            experiment_type_manager
            or ExperimentTypeManager(mode_manager=self.experiment_mode_manager)
        )

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
            experiment_mode_manager=self.experiment_mode_manager,
            experiment_type_manager=self.experiment_type_manager,
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

    def stop(self) -> bool:
        """停止后端服务；活动实验必须先完成正常安全停机。"""
        if not self._started:
            return True

        if not self._stop_active_experiment():
            return False

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

        # 先停止数据处理器，避免关闭设备串口时采集线程仍在读取
        if self.data_handler:
            try:
                self.data_handler.stop()
            except Exception as e:
                self.logger.error(f"关闭数据处理器出错: {e}")

        # 停止设备管理器
        devices_released = True
        if self.device_manager:
            try:
                devices_released = self.device_manager.stop_all() is not False
            except Exception as e:
                devices_released = False
                self.logger.error(f"关闭设备管理器出错: {e}")
        self._devices_released = devices_released

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
        return True

    def restart(self) -> bool:
        """重启后端服务（用于应用新的通信配置）。"""
        if not self.stop():
            return False

        # 上一代设备线程若仍在运行，它们还占着同一批 COM 口：此时重建会与孤儿
        # 线程抢端口，谁先 CreateFile 谁赢，失败方将永久处于“设备未连接”。
        if not getattr(self, "_devices_released", True):
            self.logger.critical(
                "上一代设备线程未能释放串口，已取消重建；请重启应用以恢复设备通信。"
            )
            return False

        try:
            self.start()
        except Exception as exc:
            self.logger.critical(f"重建运行时服务失败，服务已停止: {exc}", exc_info=True)
            return False
        return self._started

    def apply_comm_settings(self) -> bool:
        """应用通信配置变更。"""
        return self.restart()

    def _stop_active_experiment(self) -> bool:
        """Run the controller stop path before tearing down runtime services."""
        experiment_runtime = self.experiment_runtime
        if experiment_runtime is None:
            return True

        get_controller = getattr(experiment_runtime, "get_controller", None)
        if not callable(get_controller):
            return True

        controller = get_controller()
        if controller is None or not controller.is_experiment_running():
            return True

        self.logger.warning("运行时关闭前检测到活动实验，正在执行安全停机")
        try:
            stopped = bool(experiment_runtime.stop_experiment())
        except Exception as exc:
            self.logger.critical(
                f"活动实验安全停机异常，已取消运行时关闭: {exc}",
                exc_info=True,
            )
            return False

        if not stopped:
            self.logger.critical("活动实验安全停机失败，已取消运行时关闭")
            return False
        return True

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
        return ExperimentRuntime(
            device_manager,
            data_handler,
            parent,
            experiment_mode_manager=self.experiment_mode_manager,
            experiment_type_manager=self.experiment_type_manager,
        )

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
