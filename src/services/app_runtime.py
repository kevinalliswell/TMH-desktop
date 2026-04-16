import logging

from PySide6.QtCore import QObject, QTimer, Signal

from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler
from src.services.experiment_runtime import ExperimentRuntime
from src.utils.path_manager import PathManager


class AppRuntime(QObject):
    """应用运行时服务，管理设备与数据采集生命周期。"""

    comm_status_updated = Signal(bool, str, str)

    def __init__(self, parent=None, save_interval=60):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.device_manager = None
        self.data_handler = None
        self.experiment_runtime = None
        self.comm_status_timer = None
        self.save_interval = save_interval
        self._started = False

    def start(self):
        """初始化并启动后端服务。"""
        if self._started:
            return
        db_path = PathManager.get_data_path("device_data.db")
        PathManager.ensure_file_directory_exists(db_path)

        self.device_manager = DeviceManager()
        self.data_handler = DataHandler(db_path=db_path, save_interval=self.save_interval)
        self.data_handler.set_device_manager(self.device_manager)
        self.experiment_runtime = ExperimentRuntime(self.device_manager, self.data_handler, self)

        self._register_real_devices()

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

        self._started = False

    def restart(self):
        """重启后端服务（用于应用新的通信配置）。"""
        self.stop()
        self.start()

    def apply_comm_settings(self):
        """应用通信配置变更。"""
        self.restart()

    def _register_real_devices(self):
        """注册真实设备"""
        from src.device_clients.balance_client import BalanceClient
        from src.device_clients.temp_client import TempClient
        from src.device_clients.multi_mfc_client import MultiMFCClient

        config_path = PathManager.get_config_path("comm_config.json")

        try:
            balance_client = BalanceClient(config_path)
            self.device_manager.register_device("Balance", balance_client)
            self.logger.info("天平设备注册成功")
        except Exception as e:
            self.logger.error(f"天平设备注册失败: {e}")

        try:
            temp_client = TempClient(config_path)
            self.device_manager.register_device("Temp", temp_client)
            self.logger.info("温度控制设备注册成功")
        except Exception as e:
            self.logger.error(f"温度控制设备注册失败: {e}")

        try:
            mfc_client = MultiMFCClient(config_path)
            self.device_manager.register_device("MFC", mfc_client)
            self.logger.info("MFC设备注册成功")
        except Exception as e:
            self.logger.error(f"MFC设备注册失败: {e}")

    def _check_communication_status(self):
        try:
            is_connected, device_names, error_msg = self.device_manager.get_connection_status()
            self.comm_status_updated.emit(is_connected, device_names, error_msg)
        except Exception as e:
            self.logger.error(f"通信状态检查出错: {e}")
            self.comm_status_updated.emit(False, "", str(e))
