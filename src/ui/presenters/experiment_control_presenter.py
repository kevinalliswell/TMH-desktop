from __future__ import annotations

import os


class ExperimentControlPresenter:
    """Coordinates IntegratedControlPage actions without embedding flow logic in the view."""

    def __init__(self, view, experiment_api, workflow_service, logger):
        self.view = view
        self.experiment_api = experiment_api
        self.workflow_service = workflow_service
        self.logger = logger

    def handle_start_experiment(self) -> None:
        self.logger.info(f"开始实验:{self.workflow_service.device_manager}")
        try:
            experiment_params = self.view.request_experiment_parameters()
            if not experiment_params:
                return

            self.logger.info(f"实验参数: {experiment_params}")

            if not self.view.ensure_experiment_ready():
                return

            start_result = self.workflow_service.start_experiment(experiment_params)
            if not start_result.success:
                self.view.show_error("错误", start_result.message)
                return

            self.logger.info(f"实验对话框参数设置的数据: {start_result.experiment_data}")
            self.view.begin_experiment_session(
                experiment_data=start_result.experiment_data,
                experiment_file_path=start_result.experiment_file_path,
                experiment_params=experiment_params,
            )

            filename = os.path.basename(start_result.experiment_file_path or "")
            self.view.show_info("成功", f"实验已开始！\n\n实验文件：{filename}")
        except Exception as exc:
            self.view.show_error("错误", f"开始实验时发生错误：{exc}")
            self.logger.error(f"开始实验失败：{exc}")

    def handle_stop_experiment(self) -> None:
        try:
            if not self.experiment_api.is_experiment_running():
                self.view.show_warning("提示", "没有正在运行的实验")
                return

            if not self.view.confirm(
                "停止实验确认",
                "确定要停止实验吗？数据采集将终止！",
                default_no=True,
            ):
                return

            if self.view.has_exportable_data() and self.view.confirm(
                "保存数据确认",
                "停止实验前是否需要保存数据？",
                default_no=True,
            ):
                self.handle_save_data()

            stop_result = self.workflow_service.stop_experiment()
            if not stop_result.success:
                self.view.show_error("错误", stop_result.message)
        except Exception as exc:
            self.view.show_error("错误", f"停止实验时发生错误：{exc}")
            self.logger.error(f"停止实验失败：{exc}")

    def handle_gas_flow_set(self, gas_symbol: str, flow_value: float) -> None:
        self.logger.info(f"处理气体流量设置信号: {gas_symbol}, {flow_value:.2f}")
        self.logger.info(f"设备管理器: {self.workflow_service.device_manager}")
        self.logger.info("实验控制器由实验外观服务管理")
        try:
            if not self.workflow_service.device_manager:
                self.view.show_warning("操作提示", "设备管理器未初始化，无法设置气体流量")
                return

            success = self.experiment_api.control_gas_flow(gas_symbol, flow_value)
            if success:
                self.logger.info(f"设置{gas_symbol}流量成功: {flow_value:.2f}L/min")
                return

            self.logger.error(f"设置{gas_symbol}流量失败: {flow_value:.2f}L/min")
            self.view.set_status_message(f"设置{gas_symbol}流量失败: {flow_value:.2f}L/min")
        except Exception as exc:
            self.view.show_error("错误", f"设置{gas_symbol}流量时发生错误：{exc}")
            self.logger.error(f"设置{gas_symbol}流量失败：{exc}")
            self.view.set_status_message(f"设置{gas_symbol}流量失败: {exc}")

    def handle_tare_balance(self) -> None:
        self.logger.info("处理天平清零信号")
        try:
            if not self.workflow_service.device_manager:
                self.view.show_warning("操作提示", "设备管理器未初始化，无法进行天平清零")
                return

            success = self.experiment_api.tare_balance(self.view.dialog_parent())
            if success:
                self.logger.info("天平清零成功")
                self.view.set_status_message("天平清零成功")
                return

            self.logger.error("天平清零失败")
            self.view.set_status_message("天平清零失败")
        except Exception as exc:
            self.view.show_error("错误", f"天平清零时发生错误：{exc}")
            self.logger.error(f"天平清零失败：{exc}")
            self.view.set_status_message(f"天平清零失败: {exc}")

    def handle_save_data(self) -> None:
        self.logger.info("处理保存数据信号")
        try:
            if not self.view.has_exportable_data():
                self.view.show_warning("操作提示", "没有数据可保存，请先运行实验")
                return

            success = self.view.export_current_data()
            if success:
                self.logger.info("实验数据导出成功")
                self.view.set_status_message("实验数据导出成功")
                return

            self.logger.warning("用户取消了数据导出")
            self.view.set_status_message("数据导出已取消")
        except Exception as exc:
            self.view.show_error("错误", f"保存数据时发生错误：{exc}")
            self.logger.error(f"保存数据失败：{exc}")
            self.view.set_status_message(f"保存数据失败: {exc}")

    def handle_reset_experiment(self) -> None:
        self.logger.info("处理实验重置信号")
        if not self.view.confirm(
            "重置实验确认",
            "确定要重置实验吗？所有数据将被清除！",
            default_no=True,
        ):
            return

        if self.view.confirm("保存数据确认", "确定要保存数据吗？", default_no=True):
            self.handle_save_data()

        try:
            if self.experiment_api.is_experiment_running():
                stop_result = self.workflow_service.stop_experiment()
                if not stop_result.success:
                    self.view.show_error("错误", stop_result.message)
                    return

            self.view.reset_flow_display()

            safety_result = self.workflow_service.apply_protective_gas()
            if not safety_result.success:
                self.view.show_error("错误", safety_result.message)
                return

            self.view.clear_experiment_data_view()
            self.view.show_info("成功", "实验已重置，已切换到N₂保护气氛")
            self.logger.info("实验重置成功")
            self.view.set_status_message("实验重置成功")
        except Exception as exc:
            self.view.show_error("错误", f"重置实验时发生错误：{exc}")
            self.logger.error(f"重置实验失败：{exc}")
            self.view.set_status_message(f"重置实验失败: {exc}")

    def handle_set_initial_weight(self) -> None:
        self.logger.info("处理设置初始重量信号")
        try:
            if not self.experiment_api.get_controller():
                error_msg = "实验控制器未初始化，无法设置初始重量"
                self.logger.error(error_msg)
                self.view.show_warning("操作提示", error_msg)
                self.view.set_status_message(error_msg)
                return

            success = self.experiment_api.manual_set_initial_weight(self.view.dialog_parent())
            if success:
                self.logger.info("设置初始重量流程成功完成")
                self.view.set_status_message("初始重量设置成功，已启用失重计算")
                return

            self.logger.error("设置初始重量流程失败")
            self.view.set_status_message("设置初始重量失败")
        except Exception as exc:
            error_msg = f"设置初始重量时发生错误：{exc}"
            self.view.show_error("错误", error_msg)
            self.logger.error(error_msg)
            self.view.set_status_message(f"设置初始重量失败: {exc}")
