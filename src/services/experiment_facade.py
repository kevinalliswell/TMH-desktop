from src.services.experiment_runtime import ExperimentRuntime


class ExperimentFacade:
    """面向 UI 的实验接口，屏蔽运行时细节。"""

    def __init__(self, runtime: ExperimentRuntime):
        self._runtime = runtime

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
    def experiment_completed(self):
        return self._runtime.experiment_completed

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
        """确保控制器已创建。"""
        return self._runtime.ensure_controller(
            confirm_callback=confirm_callback,
            input_double_callback=input_double_callback,
        )

    def check_experiment_params(self) -> bool:
        return self._runtime.check_experiment_params()

    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        return self._runtime.set_experiment_mode_by_id(mode_id)

    def reload_experiment_modes(self) -> None:
        self._runtime.reload_experiment_modes()

    def get_experiment_type_manager(self):
        return self._runtime.experiment_type_manager

    def start_experiment(self, experiment_record=None) -> bool:
        return self._runtime.start_experiment(experiment_record)

    def stop_experiment(self) -> bool:
        return self._runtime.stop_experiment()

    def get_stage_realignment_context(self):
        return self._runtime.get_stage_realignment_context()

    def skip_to_next_stage(self) -> bool:
        return self._runtime.skip_to_next_stage()

    def adjust_current_stage_elapsed(self, elapsed_minutes: float) -> bool:
        return self._runtime.adjust_current_stage_elapsed(elapsed_minutes)

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

    def get_controller(self):
        return self._runtime.get_controller()
