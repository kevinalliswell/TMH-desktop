# src/ui/pages/integrated_control_page.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTabWidget, QMessageBox, QDialog, QInputDialog
from PySide6.QtCore import Qt
import time

from src.ui.ui_components.chart_tabs import ChartTabs
from src.ui.ui_components.control_panel import ControlPanel
from src.ui.ui_components.monitor_panel import MonitorPanel
from src.ui.ui_components.experiment_status import ExperimentStatus
from src.ui.dialogs.experiment_dialog import ExperimentDialog
from src.models.experiment_state import ExperimentPhase
from src.services.experiment_file import ExperimentFile
from src.services.database import ExperimentData
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

    def __init__(self, device_manager, data_handler, parent=None, experiment_backend=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.data_handler = data_handler
        self.experiment_api = ExperimentFacade(
            experiment_backend or ExperimentRuntime(device_manager, data_handler, self)
        )
        self._experiment_api_signals_connected = False

        self.logger = get_logger(__name__)
        
        # 实验文件管理器
        self.experiment_file_manager = ExperimentFile()
        
        # 实验类型管理器
        self.experiment_type_manager = ExperimentTypeManager()

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
        self.control_panel = ControlPanel()
        splitter.addWidget(self.control_panel)

        splitter.setSizes([900, 300])
        main_layout.addWidget(splitter)

    def _connect_signals(self):
        # 绑定 DataHandler → UI
        self.logger.debug("信号连接成功！")
        if self.data_handler:
            # 实时数据信号 → 监控面板
            self.data_handler.all_data_updated.connect(self.update_ui_with_snapshot)
            # 实验数据信号 → 图表和数据表格
            self.data_handler.experiment_data_sampled.connect(self.update_experiment_data)
        
        # 连接控制面板信号：监听信号，处理信号
        if self.control_panel:
            self.control_panel.start_experiment.connect(self.handle_start_experiment)   # 监听信号，处理开始实验逻辑
            self.control_panel.stop_experiment.connect(self.handle_stop_experiment)   # 监听信号，处理停止实验逻辑
            self.control_panel.gas_flow_set.connect(self.handle_gas_flow_set)   # 监听信号，处理气体流量设置逻辑
            self.control_panel.tare_balance.connect(self.handle_tare_balance)   # 监听信号，处理天平清零逻辑
            self.control_panel.save_data.connect(self.handle_save_data)   # 监听信号，处理保存数据逻辑
            self.control_panel.reset_experiment.connect(self.handle_reset_experiment)   # 监听信号，处理实验重置逻辑
            self.control_panel.set_initial_weight.connect(self.handle_set_initial_weight)   # 监听信号，处理设置初始重量逻辑

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
        self.logger.info(f"开始实验:{self.device_manager}")
        try:
            # 1. 检查设备状态
            if not self._check_device_availability():
                return
            
            # 2. 获取实验参数
            experiment_params = self._get_experiment_parameters()
            if not experiment_params:
                return

            self.logger.info(f"实验参数: {experiment_params}")
            
            # 3. 创建并保存实验数据
            experiment_data, filepath = self._create_and_save_experiment_data(experiment_params)
            if not experiment_data:
                return

            self.logger.info(f"实验对话框参数设置的数据: {experiment_data}")

            # 4. 初始化实验控制器
            if not self._initialize_experiment_facade():
                return
            
            # 5. 设置实验模式
            if not self._setup_experiment_mode(experiment_params):
                return

            # 6. 启动实验
            if not self.experiment_api.start_experiment():
                QMessageBox.critical(self, "错误", "启动实验失败！")
                return

            # === 启动成功后才执行 UI 和数据采集的初始化 ===

            # 启动数据采集线程，备份原始数据
            self.data_handler.start_save_db_thread()
            
            # 启用表格数据写入
            self.chart_tabs.enable_table_data_writing()
            
            # 设置实验信息到图表组件
            experiment_info = self._format_experiment_data_to_info(experiment_data)
            self.chart_tabs.set_experiment_info(experiment_info)

            # 更新UI状态（按钮由 _on_state_changed 统一管理）
            self.experiment_status.update_experiment_info(experiment_params)

            import os
            filename = os.path.basename(filepath)
            QMessageBox.information(self, "成功", f"实验已开始！\n\n实验文件：{filename}")
            self.logger.info("实验已成功启动")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始实验时发生错误：{str(e)}")
            self.logger.error(f"开始实验失败：{str(e)}")

    def _check_device_availability(self):
        """检查设备可用性"""
        if not self.device_manager:
            QMessageBox.warning(self, "操作提示", "设备管理器未初始化！")
            return False
        
        # 检查所有设备是否有数据
        device_statuses = self.device_manager.get_all_status()
        devices_without_data = []
        
        for device_name, status in device_statuses.items():
            if not status.get("running", False):
                devices_without_data.append(f"{device_name} (未运行)")
                continue
            
            # 检查设备是否有最新数据
            last_update_ts = status.get("last_update_ts")
            if last_update_ts is None:
                devices_without_data.append(f"{device_name} (无数据)")
                continue
            
            # 检查数据是否过期（超过10秒认为过期）
            current_time = time.time()
            if current_time - last_update_ts > 10:
                devices_without_data.append(f"{device_name} (数据过期)")
                self.logger.warning(f"设备 {device_name} 数据过期: {current_time - last_update_ts:.1f}秒前")
        
        if devices_without_data:
            device_list = "\n".join(devices_without_data)
            QMessageBox.warning(self, "操作提示", 
                f"以下设备无数据或数据过期，无法开始实验：\n\n{device_list}\n\n"
                "请确保所有设备正常运行并获取到最新数据后再开始实验。")
            return False
        
        # 所有设备都有数据，可以开始实验
        self.logger.info(f"所有设备数据检查通过，共检查 {len(device_statuses)} 个设备")
        return True

    def _get_experiment_parameters(self):
        """获取实验参数"""
        dialog = ExperimentDialog(self)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_experiment_params()
        return None

    def _create_and_save_experiment_data(self, experiment_params):
        """创建并保存实验数据"""
        import uuid
        from datetime import datetime
        
        # 创建实验数据对象
        experiment_data = ExperimentData(
            experiment_id=str(uuid.uuid4()),
            experiment_name=experiment_params["project_name"],
            sample_name=experiment_params["sample_name"],
            sample_weight=experiment_params["sample_weight"],
            start_time=datetime.now().isoformat(),
            description=experiment_params["notes"],
            operator=experiment_params["operator"],
            experiment_type=experiment_params["experiment_type"]
        )

        self.logger.info(f"实验数据: {experiment_data}")
        
        # 生成实验文件名
        filename = self.experiment_file_manager.generate_filename(experiment_data)
        
        # 确保实验文件目录存在
        from src.utils.path_manager import PathManager
        experiments_dir = PathManager.get_data_path("experiments")
        import os
        os.makedirs(experiments_dir, exist_ok=True)
        filepath = os.path.join(experiments_dir, filename)
        
        # 保存实验文件
        if self.experiment_file_manager.save_experiment(filepath, experiment_data):
            self.logger.info(f"实验文件已保存：{filepath}")
            return experiment_data, filepath
        else:
            QMessageBox.critical(self, "错误", "保存实验文件失败！")
            return None, None

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

    def _setup_experiment_mode(self, experiment_params):
        """设置实验模式"""
        try:
            # 根据实验模式ID设置实验类型
            mode_id = experiment_params.get("experiment_mode_id")
            if not mode_id:
                QMessageBox.critical(self, "错误", "实验模式ID不能为空！")
                return False
            
            # 使用实验控制器的统一方法设置实验模式
            if self.experiment_api.set_experiment_mode_by_id(mode_id):
                # 获取类型信息用于日志
                type_info = self.experiment_type_manager.get_type_by_id(mode_id)
                if type_info:
                    self.logger.info(f"设置实验模式成功: {type_info.name}")
                else:
                    self.logger.info(f"设置实验模式成功: {mode_id}")
                return True
            else:
                QMessageBox.critical(self, "错误", "设置实验模式失败！")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置实验模式失败：{str(e)}")
            return False

    def handle_stop_experiment(self):
        """处理停止实验按钮点击"""
        try:
            if not self.experiment_api.is_experiment_running():
                QMessageBox.warning(self, "提示", "没有正在运行的实验")
                return

            # 停止实验前，务必确认
            reply = QMessageBox.question(
                self,
                "停止实验确认",
                "确定要停止实验吗？数据采集将终止！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

            # 询问是否保存数据
            if self.chart_tabs and self.chart_tabs.get_table_data_count() > 0:
                save_reply = QMessageBox.question(
                    self,
                    "保存数据确认",
                    "停止实验前是否需要保存数据？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if save_reply == QMessageBox.Yes:
                    self.handle_save_data()

            # 停止实验控制器（清理由 _on_state_changed → _on_experiment_ended_cleanup 统一执行）
            self.experiment_api.stop_experiment()
            self.logger.info("实验已停止")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"停止实验时发生错误：{str(e)}")
            self.logger.error(f"停止实验失败：{str(e)}")

    def _on_state_changed(self, state):
        """
        集中式状态驱动 UI 更新。

        所有按钮启用/禁用、状态面板更新都从此处派生，
        取代之前分散在各处的 setEnabled() 调用。
        实验结束时的清理也在此处统一执行。
        """
        is_running = state.is_running
        is_idle = state.phase == ExperimentPhase.IDLE

        # 跟踪是否曾处于活跃状态（用于区分初始 IDLE 和实验结束后的 IDLE）
        if state.is_active:
            self._was_experiment_active = True

        # 按钮状态：从实验阶段派生
        self.control_panel.start_btn.setEnabled(is_idle)
        self.control_panel.stop_btn.setEnabled(is_running)

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
        if self.data_handler:
            self.data_handler.stop_save_db_thread()
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
        """
        处理气体流量设置信号
        
        Args:
            gas_symbol: 气体符号 (N2, CO, CO2, H2)
            flow_value: 流量值 (L/min)
        """
        self.logger.info(f"处理气体流量设置信号: {gas_symbol}, {flow_value:.2f}")
        self.logger.info(f"设备管理器: {self.device_manager}")
        self.logger.info("实验控制器由实验外观服务管理")
        try:
            # 检查设备管理器是否可用
            if not self.device_manager:
                QMessageBox.warning(self, "操作提示", "设备管理器未初始化，无法设置气体流量")
                return
            
            success = self.experiment_api.control_gas_flow(gas_symbol, flow_value)
            if success:
                self.logger.info(f"设置{gas_symbol}流量成功: {flow_value:.2f}L/min")
            else:
                self.logger.error(f"设置{gas_symbol}流量失败: {flow_value:.2f}L/min")
                self.experiment_status.set_status(experiment_status=f"设置{gas_symbol}流量失败: {flow_value:.2f}L/min")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置{gas_symbol}流量时发生错误：{str(e)}")
            self.logger.error(f"设置{gas_symbol}流量失败：{str(e)}")
            self.experiment_status.set_status(experiment_status=f"设置{gas_symbol}流量失败: {str(e)}")
    
    def handle_tare_balance(self):
        """
        处理天平清零信号 - 带确认对话框
        """
        self.logger.info("处理天平清零信号")
        try:
            # 检查设备管理器是否可用
            if not self.device_manager:
                QMessageBox.warning(self, "操作提示", "设备管理器未初始化，无法进行天平清零")
                return
            
            success = self.experiment_api.tare_balance(self)
            if success:
                self.logger.info("天平清零成功")
                self.experiment_status.set_status(experiment_status="天平清零成功")
            else:
                self.logger.error("天平清零失败")
                self.experiment_status.set_status(experiment_status="天平清零失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"天平清零时发生错误：{str(e)}")
            self.logger.error(f"天平清零失败：{str(e)}")
            self.experiment_status.set_status(experiment_status=f"天平清零失败: {str(e)}")
    
    def handle_save_data(self):
        """
        处理保存数据信号
        """
        self.logger.info("处理保存数据信号")
        try:
            # 检查是否有数据可保存
            if not self.chart_tabs or self.chart_tabs.get_table_data_count() == 0:
                QMessageBox.warning(self, "操作提示", "没有数据可保存，请先运行实验")
                return
            
            # 获取当前实验信息
            experiment_info = self._get_current_experiment_info()
            
            # 显示导出对话框
            success = self.chart_tabs.show_export_dialog(experiment_info)
            
            if success:
                self.logger.info("实验数据导出成功")
                self.experiment_status.set_status(experiment_status="实验数据导出成功")
            else:
                self.logger.warning("用户取消了数据导出")
                self.experiment_status.set_status(experiment_status="数据导出已取消")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存数据时发生错误：{str(e)}")
            self.logger.error(f"保存数据失败：{str(e)}")
            self.experiment_status.set_status(experiment_status=f"保存数据失败: {str(e)}")
    
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
        """
        处理实验重置信号
        """
        self.logger.info("处理实验重置信号")
        # 重置前确认操作
        reply = QMessageBox.question(
            self,
            "重置实验确认",
            "确定要重置实验吗？所有数据将被清除！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        # 确认是否需要保存数据
        reply = QMessageBox.question(
            self,
            "保存数据确认",
            "确定要保存数据吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.handle_save_data()

        try:
            # 检查是否有正在运行的实验
            if self.experiment_api.is_experiment_running():
                # 先停止实验（通用清理由 _on_state_changed → _on_experiment_ended_cleanup 执行）
                self.experiment_api.stop_experiment()
                self.logger.info("实验已停止")
            
            # === 以下为重置特有的操作 ===
            
            # 重置气体流量显示
            if self.control_panel:
                self.control_panel.set_gas_flow_value('N2', 0.0)
                self.control_panel.set_gas_flow_value('CO', 0.0)
                self.control_panel.set_gas_flow_value('CO2', 0.0)
                self.control_panel.set_gas_flow_value('H2', 0.0)
            
            # 设置安全气氛
            if self.device_manager:
                self.device_manager.set_flow('N2', 5.0)  # 5L/min N2保护
                self.device_manager.set_flow('CO', 0.0)
                self.device_manager.set_flow('CO2', 0.0)
                self.device_manager.set_flow('H2', 0.0)

            # 清空实验数据
            if self.chart_tabs:
                self.chart_tabs.clear_table_data()
                self.logger.info("图表数据已清空")
            
            QMessageBox.information(self, "成功", "实验已重置，已切换到N₂保护气氛")
            self.logger.info("实验重置成功")
            self.experiment_status.set_status(experiment_status="实验重置成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重置实验时发生错误：{str(e)}")
            self.logger.error(f"重置实验失败：{str(e)}")
            self.experiment_status.set_status(experiment_status=f"重置实验失败: {str(e)}")
   
    def handle_set_initial_weight(self):
        """
        处理设置初始重量信号 - 优化版本
        通过实验控制器执行完整的设置流程：天平去皮 → 输入样品重量 → 计算总重量
        """
        self.logger.info("处理设置初始重量信号")
        try:
            # 检查实验控制器是否可用
            if not self.experiment_api.get_controller():
                error_msg = "实验控制器未初始化，无法设置初始重量"
                self.logger.error(error_msg)
                QMessageBox.warning(self, "操作提示", error_msg)
                self.experiment_status.set_status(experiment_status=error_msg)
                return
            
            # 通过实验控制器执行优化的设置初始重量流程
            success = self.experiment_api.manual_set_initial_weight(self)
            
            if success:
                self.logger.info("设置初始重量流程成功完成")
                self.experiment_status.set_status(experiment_status="初始重量设置成功，已启用失重计算")
            else:
                self.logger.error("设置初始重量流程失败")
                self.experiment_status.set_status(experiment_status="设置初始重量失败")
                
        except Exception as e:
            error_msg = f"设置初始重量时发生错误：{str(e)}"
            QMessageBox.critical(self, "错误", error_msg)
            self.logger.error(error_msg)
            self.experiment_status.set_status(experiment_status=f"设置初始重量失败: {str(e)}")



