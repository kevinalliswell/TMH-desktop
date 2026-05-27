#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# test_ui_signal.py
"""
UI界面与业务层通信测试脚本
演示系统中各个层次之间的信号槽通信机制

通信层次架构：
┌─────────────────┐
│   UI Layer      │  ←→  PySide6 Signals/Slots
├─────────────────┤
│ Application     │  ←→  DeviceService
├─────────────────┤
│ Business Logic  │  ←→  ExperimentController, ExperimentManager
├─────────────────┤
│ Data Processing │  ←→  DataHandler
├─────────────────┤
│ Device Layer    │  ←→  DeviceManager, Device Clients
└─────────────────┘
"""

import sys
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                               QTabWidget, QGroupBox, QGridLayout,
                               QProgressBar)
from PySide6.QtCore import (Signal, Slot, QTimer, QThread, Qt)
from PySide6.QtGui import QFont

# 导入系统组件
from src.application.device_service import DeviceService
from src.controllers.experiment_controller import ExperimentController
from src.device_clients.data_handler import DataHandler
from src.device_clients.device_manager import DeviceManager
from src.ui.ui_components.control_panel import ControlPanel
from src.ui.ui_components.monitor_panel import MonitorPanel


class CommunicationDemo(QMainWindow):
    """UI通信演示主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMH系统 - UI与业务层通信演示")
        self.setGeometry(100, 100, 1400, 900)
        
        # 初始化业务层组件
        self._init_business_layers()
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号槽
        self._connect_signals()
        
        # 启动演示
        self._start_demo()
    
    def _init_business_layers(self):
        """初始化业务层组件"""
        print("🔧 初始化业务层组件...")
        
        # 1. 设备管理器
        self.device_manager = DeviceManager()
        
        # 2. 数据处理器
        self.data_handler = DataHandler(db_path=":memory:", save_interval=5)
        self.data_handler.set_device_manager(self.device_manager)
        
        # 3. 设备服务层
        self.device_service = DeviceService(test_mode=True)
        
        # 4. 实验控制器
        self.experiment_controller = ExperimentController(self.device_manager)
        
        print("✅ 业务层组件初始化完成")
    
    def _init_ui(self):
        """初始化UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("🔗 TMH系统 - UI与业务层通信演示")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                color: white;
                padding: 15px;
                border-radius: 8px;
                margin: 5px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 1. 设备通信演示
        self.device_tab = self._create_device_communication_tab()
        self.tab_widget.addTab(self.device_tab, "🔌 设备通信")
        
        # 2. 实验控制演示
        self.experiment_tab = self._create_experiment_control_tab()
        self.tab_widget.addTab(self.experiment_tab, "🧪 实验控制")
        
        # 3. 数据处理演示
        self.data_tab = self._create_data_processing_tab()
        self.tab_widget.addTab(self.data_tab, "📊 数据处理")
        
        # 4. UI组件通信演示
        self.ui_tab = self._create_ui_communication_tab()
        self.tab_widget.addTab(self.ui_tab, "🎨 UI组件通信")
        
        # 5. 完整流程演示
        self.flow_tab = self._create_complete_flow_tab()
        self.tab_widget.addTab(self.flow_tab, "🔄 完整流程")
        
        main_layout.addWidget(self.tab_widget)
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("系统就绪")
    
    def _create_device_communication_tab(self):
        """创建设备通信演示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("""
        <h3>设备通信层演示</h3>
        <p>演示 DeviceService 与 DeviceManager 之间的通信：</p>
        <ul>
        <li>UI → DeviceService (槽函数调用)</li>
        <li>DeviceService → UI (信号发送)</li>
        <li>设备状态监控</li>
        <li>设备命令执行</li>
        </ul>
        """)
        info_label.setStyleSheet("QLabel { background-color: #ecf0f1; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 控制按钮
        control_group = QGroupBox("设备控制")
        control_layout = QHBoxLayout(control_group)
        
        self.register_btn = QPushButton("注册设备")
        self.start_btn = QPushButton("启动设备")
        self.stop_btn = QPushButton("停止设备")
        self.status_btn = QPushButton("查询状态")
        
        control_layout.addWidget(self.register_btn)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.status_btn)
        
        layout.addWidget(control_group)
        
        # 日志显示
        log_group = QGroupBox("通信日志")
        log_layout = QVBoxLayout(log_group)
        
        self.device_log = QTextEdit()
        self.device_log.setMaximumHeight(200)
        self.device_log.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Courier New';
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.device_log)
        
        layout.addWidget(log_group)
        
        # 状态显示
        status_group = QGroupBox("设备状态")
        status_layout = QGridLayout(status_group)
        
        self.device_status_labels = {}
        devices = ["Balance", "Temp", "MFC"]
        for i, device in enumerate(devices):
            label = QLabel(f"{device}:")
            value_label = QLabel("未连接")
            value_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            
            status_layout.addWidget(label, i, 0)
            status_layout.addWidget(value_label, i, 1)
            self.device_status_labels[device] = value_label
        
        layout.addWidget(status_group)
        
        return widget
    
    def _create_experiment_control_tab(self):
        """创建实验控制演示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("""
        <h3>实验控制层演示</h3>
        <p>演示 ExperimentController 的信号槽通信：</p>
        <ul>
        <li>实验状态管理</li>
        <li>阶段自动切换</li>
        <li>设备控制集成</li>
        <li>实验数据管理</li>
        </ul>
        """)
        info_label.setStyleSheet("QLabel { background-color: #ecf0f1; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 实验控制
        control_group = QGroupBox("实验控制")
        control_layout = QHBoxLayout(control_group)
        
        self.start_exp_btn = QPushButton("开始实验")
        self.stop_exp_btn = QPushButton("停止实验")
        self.set_mode_btn = QPushButton("设置模式")
        self.set_params_btn = QPushButton("设置参数")
        
        control_layout.addWidget(self.start_exp_btn)
        control_layout.addWidget(self.stop_exp_btn)
        control_layout.addWidget(self.set_mode_btn)
        control_layout.addWidget(self.set_params_btn)
        
        layout.addWidget(control_group)
        
        # 实验状态
        status_group = QGroupBox("实验状态")
        status_layout = QGridLayout(status_group)
        
        self.exp_status_label = QLabel("状态: 待机")
        self.exp_time_label = QLabel("用时: 00:00:00")
        self.exp_stage_label = QLabel("阶段: 无")
        
        status_layout.addWidget(self.exp_status_label, 0, 0)
        status_layout.addWidget(self.exp_time_label, 0, 1)
        status_layout.addWidget(self.exp_stage_label, 0, 2)
        
        layout.addWidget(status_group)
        
        # 实验日志
        log_group = QGroupBox("实验日志")
        log_layout = QVBoxLayout(log_group)
        
        self.experiment_log = QTextEdit()
        self.experiment_log.setMaximumHeight(150)
        log_layout.addWidget(self.experiment_log)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_data_processing_tab(self):
        """创建数据处理演示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("""
        <h3>数据处理层演示</h3>
        <p>演示 DataHandler 的数据流处理：</p>
        <ul>
        <li>实时数据采集</li>
        <li>数据信号发送</li>
        <li>数据存储管理</li>
        <li>数据可视化更新</li>
        </ul>
        """)
        info_label.setStyleSheet("QLabel { background-color: #ecf0f1; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 数据控制
        control_group = QGroupBox("数据控制")
        control_layout = QHBoxLayout(control_group)
        
        self.start_data_btn = QPushButton("开始采集")
        self.stop_data_btn = QPushButton("停止采集")
        self.clear_data_btn = QPushButton("清空数据")
        
        control_layout.addWidget(self.start_data_btn)
        control_layout.addWidget(self.stop_data_btn)
        control_layout.addWidget(self.clear_data_btn)
        
        layout.addWidget(control_group)
        
        # 数据监控面板
        self.monitor_panel = MonitorPanel()
        layout.addWidget(self.monitor_panel)
        
        # 数据日志
        log_group = QGroupBox("数据日志")
        log_layout = QVBoxLayout(log_group)
        
        self.data_log = QTextEdit()
        self.data_log.setMaximumHeight(150)
        log_layout.addWidget(self.data_log)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_ui_communication_tab(self):
        """创建UI组件通信演示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("""
        <h3>UI组件通信演示</h3>
        <p>演示UI组件之间的信号槽通信：</p>
        <ul>
        <li>ControlPanel 信号发送</li>
        <li>MonitorPanel 数据更新</li>
        <li>组件间交互</li>
        <li>实时数据绑定</li>
        </ul>
        """)
        info_label.setStyleSheet("QLabel { background-color: #ecf0f1; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 分割布局
        content_layout = QHBoxLayout()
        
        # 左侧 - 控制面板
        self.control_panel = ControlPanel()
        content_layout.addWidget(self.control_panel)
        
        # 右侧 - 监控面板
        self.monitor_panel_ui = MonitorPanel()
        content_layout.addWidget(self.monitor_panel_ui)
        
        layout.addLayout(content_layout)
        
        # 通信日志
        log_group = QGroupBox("UI通信日志")
        log_layout = QVBoxLayout(log_group)
        
        self.ui_log = QTextEdit()
        self.ui_log.setMaximumHeight(150)
        log_layout.addWidget(self.ui_log)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_complete_flow_tab(self):
        """创建完整流程演示标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info_label = QLabel("""
        <h3>完整通信流程演示</h3>
        <p>演示从UI到设备的完整通信链路：</p>
        <ul>
        <li>UI操作 → 业务逻辑 → 设备控制</li>
        <li>设备数据 → 数据处理 → UI更新</li>
        <li>实验流程自动化</li>
        <li>错误处理和状态反馈</li>
        </ul>
        """)
        info_label.setStyleSheet("QLabel { background-color: #ecf0f1; padding: 10px; border-radius: 5px; }")
        layout.addWidget(info_label)
        
        # 流程控制
        flow_group = QGroupBox("流程控制")
        flow_layout = QHBoxLayout(flow_group)
        
        self.auto_demo_btn = QPushButton("自动演示")
        self.step_demo_btn = QPushButton("步骤演示")
        self.reset_demo_btn = QPushButton("重置演示")
        
        flow_layout.addWidget(self.auto_demo_btn)
        flow_layout.addWidget(self.step_demo_btn)
        flow_layout.addWidget(self.reset_demo_btn)
        
        layout.addWidget(flow_group)
        
        # 流程状态
        status_group = QGroupBox("流程状态")
        status_layout = QGridLayout(status_group)
        
        self.flow_progress = QProgressBar()
        self.flow_status = QLabel("准备就绪")
        self.flow_step = QLabel("步骤: 0/5")
        
        status_layout.addWidget(QLabel("进度:"), 0, 0)
        status_layout.addWidget(self.flow_progress, 0, 1)
        status_layout.addWidget(self.flow_status, 0, 2)
        status_layout.addWidget(self.flow_step, 0, 3)
        
        layout.addWidget(status_group)
        
        # 完整日志
        log_group = QGroupBox("完整流程日志")
        log_layout = QVBoxLayout(log_group)
        
        self.flow_log = QTextEdit()
        self.flow_log.setMaximumHeight(200)
        log_layout.addWidget(self.flow_log)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _connect_signals(self):
        """连接信号槽"""
        print("🔗 连接信号槽...")
        
        # 设备通信信号
        self.device_service.deviceLog.connect(self._on_device_log)
        self.device_service.deviceStatus.connect(self._on_device_status)
        
        # 实验控制信号
        self.experiment_controller.status_updated.connect(self._on_experiment_status)
        self.experiment_controller.system_message_updated.connect(self._on_system_message)
        self.experiment_controller.experiment_started.connect(self._on_experiment_started)
        self.experiment_controller.experiment_stopped.connect(self._on_experiment_stopped)
        
        # 数据处理信号
        self.data_handler.all_data_updated.connect(self._on_data_updated)
        self.data_handler.communication_error.connect(self._on_communication_error)
        
        # UI组件信号
        self.control_panel.start_experiment.connect(self._on_ui_start_experiment)
        self.control_panel.stop_experiment.connect(self._on_ui_stop_experiment)
        
        # 按钮事件
        self._connect_button_events()
        
        print("✅ 信号槽连接完成")
    
    def _connect_button_events(self):
        """连接按钮事件"""
        # 设备通信按钮
        self.register_btn.clicked.connect(self._demo_register_device)
        self.start_btn.clicked.connect(self._demo_start_device)
        self.stop_btn.clicked.connect(self._demo_stop_device)
        self.status_btn.clicked.connect(self._demo_query_status)
        
        # 实验控制按钮
        self.start_exp_btn.clicked.connect(self._demo_start_experiment)
        self.stop_exp_btn.clicked.connect(self._demo_stop_experiment)
        self.set_mode_btn.clicked.connect(self._demo_set_mode)
        self.set_params_btn.clicked.connect(self._demo_set_params)
        
        # 数据控制按钮
        self.start_data_btn.clicked.connect(self._demo_start_data_collection)
        self.stop_data_btn.clicked.connect(self._demo_stop_data_collection)
        self.clear_data_btn.clicked.connect(self._demo_clear_data)
        
        # 流程控制按钮
        self.auto_demo_btn.clicked.connect(self._demo_auto_flow)
        self.step_demo_btn.clicked.connect(self._demo_step_flow)
        self.reset_demo_btn.clicked.connect(self._demo_reset_flow)
    
    def _start_demo(self):
        """启动演示"""
        print("🚀 启动通信演示...")
        self._log_flow("系统启动", "通信演示系统已就绪")
        
        # 注册虚拟设备
        self._demo_register_device()
        
        # 启动定时器用于模拟数据
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self._simulate_data)
        self.data_timer.start(1000)  # 每秒更新一次
    
    # ==================== 设备通信演示 ====================
    def _demo_register_device(self):
        """演示设备注册"""
        self._log_device("开始注册虚拟设备...")
        
        # 注册天平
        self.device_service.register_device("Balance", "balance", {"port": "COM10"})
        
        # 注册温度控制器
        self.device_service.register_device("Temp", "temp", {"port": "COM12", "slave_address": 1})
        
        # 注册MFC
        self.device_service.register_device("MFC", "mfc", {"port": "COM13", "device_addr": 1, "channels": 3})
        
        self._log_device("设备注册完成")
    
    def _demo_start_device(self):
        """演示设备启动"""
        self._log_device("启动所有设备...")
        self.device_service.start_all_devices()
    
    def _demo_stop_device(self):
        """演示设备停止"""
        self._log_device("停止所有设备...")
        self.device_service.stop_all_devices()
    
    def _demo_query_status(self):
        """演示状态查询"""
        self._log_device("查询设备状态...")
        devices = self.device_service.list_devices()
        for device in devices:
            status = self.device_service.get_status(device)
            self._log_device(f"{device}: {status}")
    
    # ==================== 实验控制演示 ====================
    def _demo_start_experiment(self):
        """演示实验开始"""
        self._log_experiment("尝试开始实验...")
        success = self.experiment_controller.start_experiment()
        if success:
            self._log_experiment("实验启动成功")
        else:
            self._log_experiment("实验启动失败 - 检查参数和设备")
    
    def _demo_stop_experiment(self):
        """演示实验停止"""
        self._log_experiment("停止实验...")
        self.experiment_controller.stop_experiment()
    
    def _demo_set_mode(self):
        """演示设置实验模式"""
        from src.services.experiment_modes import ExperimentType
        self._log_experiment("设置实验模式为GB/T 13241-2017...")
        self.experiment_controller.set_experiment_mode(ExperimentType.GB13241)
    
    def _demo_set_params(self):
        """演示设置实验参数"""
        self._log_experiment("设置实验参数...")
        # 这里可以添加参数设置逻辑
    
    # ==================== 数据处理演示 ====================
    def _demo_start_data_collection(self):
        """演示开始数据采集"""
        self._log_data("开始数据采集...")
        self.data_handler.start()
    
    def _demo_stop_data_collection(self):
        """演示停止数据采集"""
        self._log_data("停止数据采集...")
        self.data_handler.stop()
    
    def _demo_clear_data(self):
        """演示清空数据"""
        self._log_data("清空数据...")
        self.monitor_panel.update_monitor({})
    
    # ==================== 完整流程演示 ====================
    def _demo_auto_flow(self):
        """自动演示完整流程"""
        self._log_flow("开始自动演示", "将演示完整的通信流程")
        
        # 创建演示线程
        self.demo_thread = DemoThread(self)
        self.demo_thread.progress_updated.connect(self._on_demo_progress)
        self.demo_thread.step_completed.connect(self._on_demo_step)
        self.demo_thread.finished.connect(self._on_demo_finished)
        self.demo_thread.start()
    
    def _demo_step_flow(self):
        """步骤演示"""
        self._log_flow("步骤演示", "手动控制每个步骤")
        # 实现步骤控制逻辑
    
    def _demo_reset_flow(self):
        """重置演示"""
        self._log_flow("重置演示", "重置所有状态")
        self.flow_progress.setValue(0)
        self.flow_status.setText("准备就绪")
        self.flow_step.setText("步骤: 0/5")
    
    # ==================== 信号槽处理 ====================
    @Slot(str, str)
    def _on_device_log(self, device_name, message):
        """处理设备日志信号"""
        self._log_device(f"[{device_name}] {message}")
    
    @Slot(str, dict)
    def _on_device_status(self, device_name, status):
        """处理设备状态信号"""
        if device_name in self.device_status_labels:
            if status.get("running", False):
                self.device_status_labels[device_name].setText("运行中")
                self.device_status_labels[device_name].setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
            else:
                self.device_status_labels[device_name].setText("已停止")
                self.device_status_labels[device_name].setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
    
    @Slot(str)
    def _on_experiment_status(self, status):
        """处理实验状态信号"""
        self.exp_status_label.setText(f"状态: {status}")
        self._log_experiment(f"状态更新: {status}")
    
    @Slot(str)
    def _on_system_message(self, message):
        """处理系统消息信号"""
        self._log_experiment(f"系统消息: {message}")
    
    @Slot()
    def _on_experiment_started(self):
        """处理实验开始信号"""
        self._log_experiment("实验已开始")
        self.exp_time_label.setText("用时: 00:00:01")
    
    @Slot()
    def _on_experiment_stopped(self):
        """处理实验停止信号"""
        self._log_experiment("实验已停止")
    
    @Slot(dict)
    def _on_data_updated(self, data):
        """处理数据更新信号"""
        self.monitor_panel.update_monitor(data)
        self.monitor_panel_ui.update_monitor(data)
        self._log_data(f"数据更新: {len(data)} 个数据项")
    
    @Slot(str)
    def _on_communication_error(self, device_name):
        """处理通信错误信号"""
        self._log_data(f"通信错误: {device_name}")
    
    @Slot()
    def _on_ui_start_experiment(self):
        """处理UI开始实验信号"""
        self._log_ui("UI触发开始实验")
        self._demo_start_experiment()
    
    @Slot()
    def _on_ui_stop_experiment(self):
        """处理UI停止实验信号"""
        self._log_ui("UI触发停止实验")
        self._demo_stop_experiment()
    
    @Slot(int)
    def _on_demo_progress(self, progress):
        """处理演示进度"""
        self.flow_progress.setValue(progress)
    
    @Slot(str)
    def _on_demo_step(self, step):
        """处理演示步骤"""
        self.flow_status.setText(step)
    
    @Slot()
    def _on_demo_finished(self):
        """处理演示完成"""
        self._log_flow("演示完成", "所有通信流程演示完毕")
    
    # ==================== 数据模拟 ====================
    def _simulate_data(self):
        """模拟数据更新"""
        import random
        
        # 模拟温度数据
        temps = {}
        for i in range(1, 10):
            temps[f"T{i}"] = 25 + random.uniform(-2, 2) + i * 5
        
        # 模拟流量数据
        flows = {
            "N2": {"PV": 5.0 + random.uniform(-0.5, 0.5)},
            "CO": {"PV": 2.0 + random.uniform(-0.2, 0.2)},
            "CO2": {"PV": 1.0 + random.uniform(-0.1, 0.1)},
            "H2": {"PV": 0.0}
        }
        
        # 模拟重量数据
        weight = 100.0 + random.uniform(-0.1, 0.1)
        
        # 构造数据包
        data = {
            "temperatures": temps,
            "flows": flows,
            "weight": {"timestamp": datetime.now().isoformat(), "data": weight},
            "initial_weight": 100.0
        }
        
        # 发送数据更新信号
        self.data_handler.all_data_updated.emit(data)
    
    # ==================== 日志记录 ====================
    def _log_device(self, message):
        """记录设备日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.device_log.append(f"[{timestamp}] {message}")
        self._scroll_to_bottom(self.device_log)
    
    def _log_experiment(self, message):
        """记录实验日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.experiment_log.append(f"[{timestamp}] {message}")
        self._scroll_to_bottom(self.experiment_log)
    
    def _log_data(self, message):
        """记录数据日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.data_log.append(f"[{timestamp}] {message}")
        self._scroll_to_bottom(self.data_log)
    
    def _log_ui(self, message):
        """记录UI日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ui_log.append(f"[{timestamp}] {message}")
        self._scroll_to_bottom(self.ui_log)
    
    def _log_flow(self, title, message):
        """记录流程日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.flow_log.append(f"[{timestamp}] {title}: {message}")
        self._scroll_to_bottom(self.flow_log)
    
    def _scroll_to_bottom(self, text_edit):
        """滚动到文本底部"""
        text_edit.verticalScrollBar().setValue(text_edit.verticalScrollBar().maximum())


class DemoThread(QThread):
    """演示线程"""
    progress_updated = Signal(int)
    step_completed = Signal(str)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
    
    def run(self):
        """运行演示流程"""
        steps = [
            "1. 注册设备",
            "2. 启动设备",
            "3. 开始数据采集", 
            "4. 设置实验参数",
            "5. 开始实验",
            "6. 监控数据",
            "7. 停止实验",
            "8. 演示完成"
        ]
        
        for i, step in enumerate(steps):
            self.step_completed.emit(step)
            self.progress_updated.emit((i + 1) * 100 // len(steps))
            
            # 模拟步骤执行
            if "注册设备" in step:
                self.parent._demo_register_device()
            elif "启动设备" in step:
                self.parent._demo_start_device()
            elif "数据采集" in step:
                self.parent._demo_start_data_collection()
            elif "实验参数" in step:
                self.parent._demo_set_params()
            elif "开始实验" in step:
                self.parent._demo_start_experiment()
            elif "停止实验" in step:
                self.parent._demo_stop_experiment()
            
            # 等待一段时间
            self.msleep(2000)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #34495e;
        }
        QTabWidget::pane {
            border: 1px solid #bdc3c7;
            background-color: white;
        }
        QTabBar::tab {
            background-color: #ecf0f1;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 2px solid #3498db;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #bdc3c7;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #21618c;
        }
    """)
    
    # 创建主窗口
    window = CommunicationDemo()
    window.show()
    
    print("🎉 UI通信演示系统启动完成!")
    print("📋 功能说明:")
    print("   - 设备通信: 演示设备服务层的信号槽通信")
    print("   - 实验控制: 演示实验控制器的状态管理")
    print("   - 数据处理: 演示数据处理器的工作流程")
    print("   - UI组件通信: 演示UI组件间的交互")
    print("   - 完整流程: 演示端到端的通信链路")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
