# src/ui/pages/integrated_control_page.py

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTabWidget, QMessageBox, QDialog, QInputDialog
from PySide6.QtCore import Qt

from src.application.services import ExperimentWorkflowService
from src.ui.presenters import ExperimentControlPresenter
from src.ui.ui_components.chart_tabs import ChartTabs
from src.ui.ui_components.control_panel import ControlPanel
from src.ui.ui_components.monitor_panel import MonitorPanel
from src.ui.ui_components.experiment_status import ExperimentStatus
from src.ui.dialogs.experiment_dialog import ExperimentDialog
from src.models.experiment_state import ExperimentPhase
from src.services.experiment_file import ExperimentFile
from src.services.experiment_runtime import ExperimentRuntime
from src.services.experiment_facade import ExperimentFacade
from src.services.experiment_type_manager import ExperimentTypeManager

from src.utils.logger import get_logger


class IntegratedControlPage(QWidget):
    """
    集成控制页面
    - 左侧：监控面板 + 实验状态 + 曲线图
    - 右侧：实验控制面板
    """

    def __init__(
        self,
        device_manager,
        data_handler,
        parent=None,
        experiment_backend=None,
        experiment_api=None,
        device_hub=None,
        gas_safety_limits=None,
        experiment_type_manager=None,
    ):
        super().__init__(parent)
        self.device_manager = device_manager
        self.device_hub = device_hub or device_manager
        # 可燃气体（H2/CO）流量安全上限，透传给控制面板输入框上界
        self.gas_safety_limits = gas_safety_limits or {"H2": 5.0, "CO": 5.0}
        self.data_handler = data_handler
        self.experiment_api = experiment_api or ExperimentFacade(
            experiment_backend or ExperimentRuntime(device_manager, data_handler, self)
        )
        self._experiment_api_signals_connected = False
        self._control_panel_signals_connected = False
        self._connected_data_handler = None

        self.logger = get_logger(__name__)
        
        # 实验文件管理器
        self.experiment_file_manager = ExperimentFile()
        
        # 实验类型管理器
        self.experiment_type_manager = (
            experiment_type_manager
            or self.experiment_api.get_experiment_type_manager()
        )
        self.workflow_service = ExperimentWorkflowService(
            device_manager=self.device_hub,
            experiment_api=self.experiment_api,
            experiment_file_manager=self.experiment_file_manager,
            experiment_type_manager=self.experiment_type_manager,
            logger=self.logger,
        )
        self.presenter = ExperimentControlPresenter(
            view=self,
            experiment_api=self.experiment_api,
            workflow_service=self.workflow_service,
            logger=self.logger,
        )

        # 实验状态跟踪（用于数据表格记录实时状态文本）
        self._was_experiment_active = False
        self._current_experiment_status = ""
        self._current_system_message = ""
        
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # 左侧 - 使用QTabWidget
        left_tab_widget = QTabWidget()
        left_tab_widget.setTabPosition(QTabWidget.South)  # 标签在下方显示

        
        # 创建实时监控数据标签页
        monitor_widget = QWidget()
        monitor_layout = QVBoxLayout(monitor_widget)
        monitor_layout.setContentsMargins(5, 5, 5, 5)  # 减小外边距
        
        self.monitor_panel = MonitorPanel()
        self.experiment_status = ExperimentStatus()
        
        monitor_layout.addWidget(self.monitor_panel, 1)  # 监控面板占据主要空间
        monitor_layout.addWidget(self.experiment_status, 0)  # 状态信息固定大小，靠下显示
        
        # 创建实时图表标签页
        self.chart_tabs = ChartTabs()
        
        # 添加标签页
        left_tab_widget.addTab(monitor_widget, "实时监控数据")
        left_tab_widget.addTab(self.chart_tabs, "实时图表")

        splitter.addWidget(left_tab_widget)

        # 右侧
        self.control_panel = ControlPanel(gas_safety_limits=self.gas_safety_limits)
        splitter.addWidget(self.control_panel)

        splitter.setSizes([900, 300])
        main_layout.addWidget(splitter)

    def _connect_signals(self):
        # 绑定 DataHandler → UI
        self.logger.debug("信号连接成功！")
        if self._connected_data_handler and self._connected_data_handler is not self.data_handler:
            try:
                self._connected_data_handler.all_data_updated.disconnect(self.update_ui_with_snapshot)
            except (RuntimeError, TypeError):
                pass
            try:
                self._connected_data_handler.experiment_data_sampled.disconnect(self.update_experiment_data)
            except (RuntimeError, TypeError):
                pass
            self._connected_data_handler = None

        if self.data_handler and self._connected_data_handler is not self.data_handler:
            # 实时数据信号 → 监控面板
            self.data_handler.all_data_updated.connect(self.update_ui_with_snapshot)
            # 实验数据信号 → 图表和数据表格
            self.data_handler.experiment_data_sampled.connect(self.update_experiment_data)
            self._connected_data_handler = self.data_handler
        
        # 连接控制面板信号：监听信号，处理信号
        if self.control_panel and not self._control_panel_signals_connected:
            self.control_panel.start_experiment.connect(self.handle_start_experiment)   # 监听信号，处理开始实验逻辑
            self.control_panel.stop_experiment.connect(self.handle_stop_experiment)   # 监听信号，处理停止实验逻辑
            self.control_panel.skip_stage.connect(self.handle_skip_stage)
            self.control_panel.adjust_stage_elapsed.connect(self.handle_adjust_stage_elapsed)
            self.control_panel.gas_flow_set.connect(self.handle_gas_flow_set)   # 监听信号，处理气体流量设置逻辑
            self.control_panel.tare_balance.connect(self.handle_tare_balance)   # 监听信号，处理天平清零逻辑
            self.control_panel.save_data.connect(self.handle_save_data)   # 监听信号，处理保存数据逻辑
            self.control_panel.reset_experiment.connect(self.handle_reset_experiment)   # 监听信号，处理实验重置逻辑
            self.control_panel.set_initial_weight.connect(self.handle_set_initial_weight)   # 监听信号，处理设置初始重量逻辑
            self._control_panel_signals_connected = True

    def rebind_runtime(self, device_manager, data_handler, experiment_api, device_hub=None,
                       gas_safety_limits=None, experiment_type_manager=None) -> None:
        """Refresh runtime-backed dependencies after AppRuntime restart."""
        if (
            self.experiment_api
            and self.experiment_api is not experiment_api
            and self._experiment_api_signals_connected
        ):
            try:
                self.experiment_api.status_updated.disconnect(self._on_experiment_status_updated)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.system_message_updated.disconnect(self._on_system_message_updated)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.experiment_started.disconnect(self._on_experiment_started)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.experiment_stopped.disconnect(self._on_experiment_stopped)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.experiment_time_updated.disconnect(self._on_experiment_time_updated)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.stage_info_updated.disconnect(self._on_stage_info_updated)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_api.state_changed.disconnect(self._on_state_changed)
            except (RuntimeError, TypeError):
                pass
            self._experiment_api_signals_connected = False
        elif self.experiment_api is not experiment_api:
            self._experiment_api_signals_connected = False

        self.device_manager = device_manager
        self.device_hub = device_hub or device_manager
        self.data_handler = data_handler
        self.experiment_api = experiment_api
        if experiment_type_manager is not None:
            self.experiment_type_manager = experiment_type_manager
            self.workflow_service.experiment_type_manager = experiment_type_manager
        self.workflow_service.device_manager = self.device_hub
        self.workflow_service.experiment_api = self.experiment_api
        self.presenter.experiment_api = self.experiment_api

        # 通信配置应用后刷新手动控制面板的可燃气体上限
        if gas_safety_limits:
            self.gas_safety_limits = dict(gas_safety_limits)
            if getattr(self, "control_panel", None) is not None:
                self.control_panel.set_gas_limits(self.gas_safety_limits)

        self._connect_signals()

    def update_ui_with_snapshot(self, snapshot: dict):
        """更新监控面板实时显示数据"""
        frames = snapshot.get("frames") or {}
        
        # 仅在实验活跃时获取初始重量，避免无实验时误导失重计算
        initial_weight = 0.0
        if self.experiment_api.is_experiment_running():
            initial_weight = self.experiment_api.get_initial_weight() or 0.0
        
        self.monitor_panel.update_monitor(frames, initial_weight=initial_weight)
    
    def update_experiment_data(self, snapshot: dict):
        """更新实验数据（图表和数据表格）"""
        frames = snapshot.get("frames") or {}
        
        # 仅在实验活跃时获取初始重量，避免无实验时误导失重计算
        initial_weight = 0.0
        if self.experiment_api.is_experiment_running():
            initial_weight = self.experiment_api.get_initial_weight() or 0.0
        
        # 使用实时跟踪的状态文本，而非硬编码字符串
        timestamp = snapshot.get("timestamp", 0)
        self.chart_tabs.update_from_frames(
            timestamp,
            frames,
            experiment_status=self._current_experiment_status or "运行中",
            system_prompt=self._current_system_message or "",
            initial_weight=initial_weight
        )

    def handle_start_experiment(self):
        """处理开始实验按钮点击"""
        self.presenter.handle_start_experiment()

    def _get_experiment_parameters(self):
        """获取实验参数"""
        dialog = ExperimentDialog(
            self,
            experiment_type_manager=self.experiment_type_manager,
        )
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_experiment_params()
        return None

    def _initialize_experiment_facade(self):
        """初始化实验外观服务"""
        try:
            self._ensure_experiment_facade()
            self._connect_experiment_facade_signals()
            
            # 设置实验参数
            if self.experiment_api.check_experiment_params():
                return True
            else:
                QMessageBox.critical(self, "错误", "设置实验参数失败！")
                return False
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化实验外观服务失败：{str(e)}")
            return False

    def _ensure_experiment_facade(self):
        """确保实验控制器已创建，并注入 UI 交互回调"""
        # 如果底层控制器被重建，需要重新连接信号
        had_controller = self.experiment_api.get_controller() is not None
        self.experiment_api.ensure_controller(
            confirm_callback=self._confirm_action,
            input_double_callback=self._input_double,
        )
        # 控制器从无到有，需要重置信号连接标志以允许重新连接
        if not had_controller and self.experiment_api.get_controller() is not None:
            self._experiment_api_signals_connected = False

    def _connect_experiment_facade_signals(self):
        """连接实验外观信号（避免重复连接）"""
        if self._experiment_api_signals_connected:
            return
        self.experiment_api.status_updated.connect(self._on_experiment_status_updated)
        self.experiment_api.system_message_updated.connect(self._on_system_message_updated)
        self.experiment_api.experiment_started.connect(self._on_experiment_started)
        self.experiment_api.experiment_stopped.connect(self._on_experiment_stopped)
        self.experiment_api.experiment_time_updated.connect(self._on_experiment_time_updated)
        self.experiment_api.stage_info_updated.connect(self._on_stage_info_updated)
        self.experiment_api.state_changed.connect(self._on_state_changed)
        self._experiment_api_signals_connected = True

    def handle_stop_experiment(self):
        """处理停止实验按钮点击"""
        self.presenter.handle_stop_experiment()

    def handle_skip_stage(self):
        """将重启后的实验安全校正到下一个配置阶段。"""
        context = self.experiment_api.get_stage_realignment_context()
        if context is None:
            self.show_warning("无法校正阶段", "仅可在实验稳定运行时校正阶段。")
            return
        if not context["can_skip"]:
            self.show_warning(
                "无法跳过阶段",
                "当前已是最后阶段。请使用“停止实验”完成数据收尾并切换保护气氛。",
            )
            return
        if not self.experiment_api.skip_to_next_stage():
            self.show_warning("阶段未变更", "阶段跳转未执行，请查看系统消息和审计日志。")

    def handle_adjust_stage_elapsed(self):
        """询问并应用固定时长阶段的实际已用时。"""
        context = self.experiment_api.get_stage_realignment_context()
        if context is None:
            self.show_warning("无法校正时长", "仅可在实验稳定运行时校正阶段时长。")
            return
        if not context["can_adjust_elapsed"]:
            self.show_warning(
                "无法校正时长",
                "当前阶段由温度条件驱动。请在核对现场状态后使用“跳到下一阶段”。",
            )
            return

        duration = context["duration_minutes"]
        current_elapsed = min(context["elapsed_minutes"], duration)
        elapsed_minutes, accepted = QInputDialog.getDouble(
            self,
            "校正阶段时长",
            (
                f"第 {context['current_stage_index']}/{context['total_stages']} 阶段："
                f"{context['stage_description']}\n"
                "请输入现场确认的阶段已用时（分钟）："
            ),
            current_elapsed,
            0.0,
            duration,
            1,
        )
        if accepted and not self.experiment_api.adjust_current_stage_elapsed(elapsed_minutes):
            self.show_warning("时长未变更", "阶段时长校正未执行，请查看系统消息和审计日志。")

    def _on_state_changed(self, state):
        """
        集中式状态驱动 UI 更新。

        所有按钮启用/禁用、状态面板更新都从此处派生，
        取代之前分散在各处的 setEnabled() 调用。
        实验结束时的清理也在此处统一执行。
        """
        is_running = state.is_running
        is_idle = state.phase == ExperimentPhase.IDLE
        can_realign_stage = state.phase == ExperimentPhase.RUNNING

        # 跟踪是否曾处于活跃状态（用于区分初始 IDLE 和实验结束后的 IDLE）
        if state.is_active:
            self._was_experiment_active = True

        # 按钮状态：从实验阶段派生
        self.control_panel.start_btn.setEnabled(is_idle)
        self.control_panel.stop_btn.setEnabled(is_running)
        self.control_panel.skip_stage_btn.setEnabled(can_realign_stage)
        self.control_panel.adjust_stage_elapsed_btn.setEnabled(can_realign_stage)

        # 实验状态文本
        phase_text_map = {
            ExperimentPhase.IDLE: "就绪",
            ExperimentPhase.CONFIGURING: "配置中...",
            ExperimentPhase.RUNNING: "实验中",
            ExperimentPhase.STAGE_TRANSITION: "阶段切换中",
            ExperimentPhase.COMPLETING: "实验完成中...",
            ExperimentPhase.STOPPING: "停止中...",
            ExperimentPhase.ERROR: f"错误: {state.error_message}",
        }
        phase_text = phase_text_map.get(state.phase, "未知")
        self.experiment_status.set_status(stage_status=phase_text)

        # 实验结束清理：仅当从活跃状态回到 IDLE 时执行
        if is_idle and self._was_experiment_active:
            self._was_experiment_active = False
            self._on_experiment_ended_cleanup()

    def _on_experiment_ended_cleanup(self):
        """
        实验结束后的统一清理逻辑。
        由 _on_state_changed 在状态回到 IDLE 时调用，
        确保手动停止、自动完成、重置等所有路径都执行相同的清理。
        """
        self.logger.info("执行实验结束清理")
        self.experiment_status.clear_experiment_info()
        if self.chart_tabs:
            self.chart_tabs.disable_table_data_writing()
        # 重置状态跟踪文本
        self._current_experiment_status = ""
        self._current_system_message = ""

    def _on_experiment_status_updated(self, status):
        """实验状态更新信号处理"""
        self.logger.info(f"实验状态更新：{status}")
        self._current_experiment_status = status
        self.experiment_status.set_status(experiment_status=status)

    def _on_system_message_updated(self, message):
        """系统消息更新信号处理"""
        self.logger.info(f"系统消息：{message}")
        self._current_system_message = message
        self.experiment_status.set_status(experiment_status=message)

    def _on_experiment_started(self):
        """实验开始信号处理"""
        self.logger.info("实验已开始")

    def _on_experiment_stopped(self):
        """实验停止信号处理（清理由 _on_state_changed 统一执行）"""
        self.logger.info("实验已停止")

    def _on_experiment_time_updated(self, time_str):
        """实验计时更新信号处理"""
        # self.logger.debug(f"实验计时更新：{time_str}")
        self.experiment_status.set_status(time_str=time_str)
    
    def _on_stage_info_updated(self, stage_info):
        """阶段信息更新信号处理"""
        try:
            # self.logger.debug(f"阶段信息更新：{stage_info}")
            self.experiment_status.update_stage_info(stage_info)
        except Exception as e:
            self.logger.error(f"处理阶段信息更新失败：{str(e)}")

    def _confirm_action(self, title: str, message: str, default_yes: bool = True) -> bool:
        default_button = QMessageBox.Yes if default_yes else QMessageBox.No
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            default_button,
        )
        return reply == QMessageBox.Yes

    def _input_double(
        self,
        title: str,
        message: str,
        value: float,
        min_value: float,
        max_value: float,
        decimals: int,
    ):
        return QInputDialog.getDouble(
            self,
            title,
            message,
            value,
            min_value,
            max_value,
            decimals,
        )

    def handle_gas_flow_set(self, gas_symbol: str, flow_value: float):
        """处理气体流量设置信号"""
        self.presenter.handle_gas_flow_set(gas_symbol, flow_value)
    
    def handle_tare_balance(self):
        """处理天平清零信号 - 带确认对话框"""
        self.presenter.handle_tare_balance()
    
    def handle_save_data(self):
        """处理保存数据信号"""
        self.presenter.handle_save_data()
    
    def _get_current_experiment_info(self) -> dict:
        """
        获取当前实验信息
        
        Returns:
            dict: 实验信息字典
        """
        try:
            # 从图表组件获取实验信息
            experiment_info = self.chart_tabs.get_experiment_info()
            if experiment_info:
                return experiment_info
            
            # 如果没有存储的实验信息，尝试从实验运行时获取
            experiment_data = self.experiment_api.get_experiment_data()
            if experiment_data:
                return self._format_experiment_data_to_info(experiment_data)
            
            # 返回基本的实验信息
            return {
                "experiment_id": "未知",
                "experiment_name": "未知实验",
                "sample_name": "未知样品",
                "sample_weight": 0.0,
                "experiment_type": "未知类型",
                "operator": "未知操作员",
                "start_time": "",
                "end_time": "",
                "description": "无描述"
            }
            
        except Exception as e:
            self.logger.error(f"获取实验信息失败: {str(e)}")
            return {
                "experiment_id": "错误",
                "experiment_name": "获取实验信息失败",
                "sample_name": "",
                "sample_weight": 0.0,
                "experiment_type": "",
                "operator": "",
                "start_time": "",
                "end_time": "",
                "description": f"错误: {str(e)}"
            }
    
    def _format_experiment_data_to_info(self, experiment_data) -> dict:
        """
        将实验数据对象格式化为信息字典
        
        Args:
            experiment_data: 实验数据对象
            
        Returns:
            dict: 格式化的实验信息字典
        """
        try:
            info = {
                "experiment_id": getattr(experiment_data, 'experiment_id', ''),
                "experiment_name": getattr(experiment_data, 'experiment_name', ''),
                "sample_name": getattr(experiment_data, 'sample_name', ''),
                "sample_weight": getattr(experiment_data, 'sample_weight', 0.0),
                "experiment_type": getattr(experiment_data, 'experiment_type', ''),
                "operator": getattr(experiment_data, 'operator', ''),
                "start_time": getattr(experiment_data, 'start_time', ''),
                "end_time": getattr(experiment_data, 'end_time', ''),
                "description": getattr(experiment_data, 'description', '')
            }
            
            # 添加分析结果（如果有）
            if hasattr(experiment_data, 'analysis_results_json') and experiment_data.analysis_results_json:
                try:
                    import json
                    analysis_results = json.loads(experiment_data.analysis_results_json)
                    info["analysis_results"] = analysis_results
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            return info
            
        except Exception as e:
            self.logger.error(f"格式化实验数据失败: {str(e)}")
            return {
                "experiment_id": "格式化错误",
                "experiment_name": "格式化实验数据失败",
                "sample_name": "",
                "sample_weight": 0.0,
                "experiment_type": "",
                "operator": "",
                "start_time": "",
                "end_time": "",
                "description": f"格式化错误: {str(e)}"
            }
            
    def handle_reset_experiment(self):
        """处理实验重置信号"""
        self.presenter.handle_reset_experiment()
   
    def handle_set_initial_weight(self):
        """处理设置初始重量信号 - 优化版本"""
        self.presenter.handle_set_initial_weight()

    def request_experiment_parameters(self):
        """View hook for the presenter to request experiment parameters."""
        return self._get_experiment_parameters()

    def ensure_experiment_ready(self) -> bool:
        """View hook for initializing controller and signal wiring."""
        return self._initialize_experiment_facade()

    def begin_experiment_session(self, experiment_data, experiment_file_path, experiment_params: dict) -> None:
        """Apply UI-side effects after a successful experiment startup."""
        if self.chart_tabs:
            self.chart_tabs.enable_table_data_writing()
            experiment_info = self._format_experiment_data_to_info(experiment_data)
            self.chart_tabs.set_experiment_info(experiment_info)
        self.experiment_status.update_experiment_info(experiment_params)

    def confirm(self, title: str, message: str, default_no: bool = False) -> bool:
        """Presenter-facing confirmation helper."""
        default_button = QMessageBox.No if default_no else QMessageBox.Yes
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            default_button,
        )
        return reply == QMessageBox.Yes

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def set_status_message(self, message: str) -> None:
        self.experiment_status.set_status(experiment_status=message)

    def dialog_parent(self):
        return self

    def has_exportable_data(self) -> bool:
        return bool(self.chart_tabs and self.chart_tabs.get_table_data_count() > 0)

    def export_current_data(self) -> bool:
        experiment_info = self._get_current_experiment_info()
        return bool(self.chart_tabs and self.chart_tabs.show_export_dialog(experiment_info))

    def reset_flow_display(self) -> None:
        if self.control_panel:
            self.control_panel.set_gas_flow_value('N2', 0.0)
            self.control_panel.set_gas_flow_value('CO', 0.0)
            self.control_panel.set_gas_flow_value('CO2', 0.0)
            self.control_panel.set_gas_flow_value('H2', 0.0)

    def clear_experiment_data_view(self) -> None:
        if self.chart_tabs:
            self.chart_tabs.clear_table_data()
            self.logger.info("图表数据已清空")



