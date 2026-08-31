from src.services.experiment_runtime import ExperimentRuntime


class ExperimentFacade:
    """面向 UI 的实验接口，屏蔽运行时细节。"""

    def __init__(self, runtime: ExperimentRuntime):
        self._runtime = runtime
        self._signal_connections = []

    # -- 信号代理属性，方便 UI 直接 connect --
    @property
    def status_updated(self):
        return self._runtime.status_updated

    @property
    def system_message_updated(self):
        return self._runtime.system_message_updated

    @property
    def safety_alert(self):
        return self._runtime.safety_alert

    @property
    def experiment_started(self):
        return self._runtime.experiment_started

    @property
    def experiment_stopped(self):
        return self._runtime.experiment_stopped

    @property
    def experiment_time_updated(self):
        return self._runtime.experiment_time_updated

    @property
    def stage_info_updated(self):
        return self._runtime.stage_info_updated

    @property
    def state_changed(self):
        return self._runtime.state_changed

    def ensure_controller(self, confirm_callback=None, input_double_callback=None):
        """确保控制器已创建（兼容旧 API ensure_ready）"""
        return self._runtime.ensure_controller(
            confirm_callback=confirm_callback,
            input_double_callback=input_double_callback,
        )

    # 保留旧 API 别名
    ensure_ready = ensure_controller

    def connect_signals(self, status_cb, system_cb, started_cb, stopped_cb, time_cb, stage_cb,
                         state_changed_cb=None):
        """连接信号并记录连接，以便 cleanup 时断开"""
        pairs = [
            (self._runtime.status_updated, status_cb),
            (self._runtime.system_message_updated, system_cb),
            (self._runtime.experiment_started, started_cb),
            (self._runtime.experiment_stopped, stopped_cb),
            (self._runtime.experiment_time_updated, time_cb),
            (self._runtime.stage_info_updated, stage_cb),
        ]
        if state_changed_cb is not None:
            pairs.append((self._runtime.state_changed, state_changed_cb))
        for signal, slot in pairs:
            signal.connect(slot)
            self._signal_connections.append((signal, slot))

    def disconnect_signals(self):
        """断开所有通过 connect_signals 建立的连接"""
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._signal_connections.clear()

    def cleanup(self):
        """清理资源"""
        self.disconnect_signals()
        if self._runtime:
            self._runtime.cleanup()

    def check_experiment_params(self) -> bool:
        return self._runtime.check_experiment_params()

    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        return self._runtime.set_experiment_mode_by_id(mode_id)

    def start_experiment(self, experiment_record=None) -> bool:
        return self._runtime.start_experiment(experiment_record)

    def stop_experiment(self) -> bool:
        return self._runtime.stop_experiment()

    def control_gas_flow(self, gas_name: str, flow_value: float) -> bool:
        return self._runtime.control_gas_flow(gas_name, flow_value)

    def tare_balance(self, parent_widget=None, skip_confirmation=False) -> bool:
        return self._runtime.tare_balance(parent_widget, skip_confirmation=skip_confirmation)

    def manual_set_initial_weight(self, parent_widget=None) -> bool:
        return self._runtime.manual_set_initial_weight(parent_widget)

    def is_experiment_running(self) -> bool:
        return self._runtime.is_experiment_running()

    def get_experiment_data(self):
        return self._runtime.get_experiment_data()

    def get_initial_weight(self) -> float:
        return self._runtime.get_initial_weight()

    def dev_start_experiment(self) -> bool:
        return self._runtime.dev_start_experiment()

    def get_controller(self):
        return self._runtime.get_controller()
