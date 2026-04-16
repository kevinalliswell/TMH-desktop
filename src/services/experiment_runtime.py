from PySide6.QtCore import QObject, Signal

from src.controllers.experiment_controller import ExperimentController


class ExperimentRuntime(QObject):
    """实验运行时服务，管理实验控制器生命周期。"""

    status_updated = Signal(str)
    system_message_updated = Signal(str)
    experiment_started = Signal()
    experiment_stopped = Signal()
    experiment_time_updated = Signal(str)
    stage_info_updated = Signal(dict)
    state_changed = Signal(object)  # 转发状态机 state_changed 信号

    def __init__(self, device_manager, data_handler, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.data_handler = data_handler
        self._controller = None
        self._signals_connected = False

    def ensure_controller(self, confirm_callback=None, input_double_callback=None):
        """创建或获取实验控制器，并注入 UI 交互回调。"""
        if self._controller is None:
            self._controller = ExperimentController(self.device_manager, self.data_handler, self)
            # 将状态机注入到 DataHandler，让其直接查询状态
            if self.data_handler and hasattr(self._controller, 'state_machine'):
                self.data_handler.set_state_machine(self._controller.state_machine)
        if not self._signals_connected:
            self._connect_signals()
        if confirm_callback or input_double_callback:
            self._controller.set_interaction_callbacks(
                confirm_callback=confirm_callback,
                input_double_callback=input_double_callback,
            )
        return self._controller

    def get_controller(self):
        """获取实验控制器（如未创建则返回 None）。"""
        return self._controller

    def _require_controller(self):
        if self._controller is None:
            self._controller = ExperimentController(self.device_manager, self.data_handler, self)
            if self.data_handler and hasattr(self._controller, 'state_machine'):
                self.data_handler.set_state_machine(self._controller.state_machine)
        if not self._signals_connected:
            self._connect_signals()
        return self._controller

    def _connect_signals(self):
        if not self._controller or self._signals_connected:
            return
        self._controller.status_updated.connect(self.status_updated)
        self._controller.system_message_updated.connect(self.system_message_updated)
        self._controller.experiment_started.connect(self.experiment_started)
        self._controller.experiment_stopped.connect(self.experiment_stopped)
        self._controller.experiment_time_updated.connect(self.experiment_time_updated)
        self._controller.stage_info_updated.connect(self.stage_info_updated)
        # 转发状态机信号
        self._controller.state_machine.state_changed.connect(self.state_changed)
        self._signals_connected = True

    def _disconnect_signals(self):
        """断开控制器信号连接"""
        if not self._controller or not self._signals_connected:
            return
        try:
            self._controller.status_updated.disconnect(self.status_updated)
            self._controller.system_message_updated.disconnect(self.system_message_updated)
            self._controller.experiment_started.disconnect(self.experiment_started)
            self._controller.experiment_stopped.disconnect(self.experiment_stopped)
            self._controller.experiment_time_updated.disconnect(self.experiment_time_updated)
            self._controller.stage_info_updated.disconnect(self.stage_info_updated)
            self._controller.state_machine.state_changed.disconnect(self.state_changed)
        except (RuntimeError, TypeError):
            pass
        self._signals_connected = False

    def cleanup(self):
        """清理资源，断开信号，销毁控制器"""
        self._disconnect_signals()
        if self._controller:
            self._controller.cleanup()
            self._controller = None

    def check_experiment_params(self) -> bool:
        return self._require_controller().check_experiment_params()

    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        return self._require_controller().set_experiment_mode_by_id(mode_id)

    def start_experiment(self) -> bool:
        return self._require_controller().start_experiment()

    def stop_experiment(self) -> bool:
        return self._require_controller().stop_experiment()

    def control_gas_flow(self, gas_name: str, flow_value: float) -> bool:
        return self._require_controller().control_gas_flow(gas_name, flow_value)

    def tare_balance(self, parent_widget=None, skip_confirmation=False) -> bool:
        return self._require_controller().tare_balance(parent_widget, skip_confirmation=skip_confirmation)

    def manual_set_initial_weight(self, parent_widget=None) -> bool:
        return self._require_controller().manual_set_initial_weight(parent_widget)

    def is_experiment_running(self) -> bool:
        return self._require_controller().is_experiment_running()

    def get_experiment_data(self):
        return self._require_controller().get_experiment_data()

    def get_initial_weight(self) -> float:
        controller = self.get_controller()
        if controller and hasattr(controller, "initial_weight"):
            return controller.initial_weight or 0.0
        return 0.0

    def dev_start_experiment(self) -> bool:
        return self._require_controller()._dev_start_experiment()
