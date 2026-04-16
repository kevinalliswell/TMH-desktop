# src/ui/ui_components/control_panel.py
from PySide6.QtWidgets import (
    QFrame, QGroupBox, QVBoxLayout, QPushButton, QLabel,
    QHBoxLayout, QGridLayout, QMessageBox, QDoubleSpinBox
)
from PySide6.QtCore import Signal


class ControlPanel(QFrame):
    """
    实验控制面板（右侧）
    包含 实验操作、气氛控制、重量控制、数据操作
    """

    # ---- 对外信号 ----
    start_experiment = Signal()
    stop_experiment = Signal()
    # set_flow = Signal(float)
    gas_flow_set = Signal(str, float)  # 气体流量设置信号 (气体名称, 流量值)
    tare_balance = Signal()  # 天平清零信号
    set_initial_weight = Signal()  # 设置初始重量信号
    save_data = Signal()  # 保存数据信号
    reset_experiment = Signal()  # 实验重置信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.NoFrame)  # 移除边框
        self.setObjectName("controlPanel")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)  # 减少间距

        # ---- 实验操作 ----
        experiment_group = QGroupBox("实验控制")
        experiment_layout = QGridLayout(experiment_group)
        experiment_layout.setSpacing(8)  # 减少间距
        
        # 开始实验按钮
        self.start_btn = QPushButton("开始实验")
        self.start_btn.setObjectName("startExperimentBtn")
        experiment_layout.addWidget(self.start_btn, 0, 0)
        
        # 停止实验按钮
        self.stop_btn = QPushButton("停止实验")
        self.stop_btn.setObjectName("stopExperimentBtn")
        experiment_layout.addWidget(self.stop_btn, 0, 1)
        
        experiment_group.setLayout(experiment_layout)
        layout.addWidget(experiment_group)

        # 连接信号（暂时保留原有的信号连接）
        self.start_btn.clicked.connect(self.start_experiment.emit)
        self.stop_btn.clicked.connect(self.stop_experiment.emit)

        # ---- 气氛控制 ----
        atmosphere_group = QGroupBox("气氛控制")
        atmosphere_layout = QVBoxLayout(atmosphere_group)
        atmosphere_layout.setSpacing(8)  # 减少间距
        
        # 添加标题
        atmosphere_layout.addWidget(QLabel("设定气氛流量 (L/min)"))
        
        # 创建4种气体的控制行，包含不同的调节范围
        gases = [
            ("N2", "氮气", 0.0, 20.0),      # N2: 0-20 L/min
            ("CO", "一氧化碳", 0.0, 5.0),    # CO: 0-5 L/min
            ("CO2", "二氧化碳", 0.0, 15.0),  # CO2: 0-15 L/min
            ("H2", "氢气", 0.0, 5.0)         # H2: 0-5 L/min
        ]
        
        self.gas_controls = {}
        for gas_symbol, gas_name, min_val, max_val in gases:
            # 创建水平布局
            gas_layout = QHBoxLayout()
            
            # 气体标签
            gas_label = QLabel(f"{gas_symbol}:")
            gas_label.setMinimumWidth(40)
            gas_layout.addWidget(gas_label)
            
            # 使用QDoubleSpinBox替代QLineEdit
            gas_input = QDoubleSpinBox()
            gas_input.setRange(min_val, max_val)  # 设置范围
            gas_input.setDecimals(2)  # 设置小数位数
            gas_input.setSingleStep(0.1)  # 设置步长
            gas_input.setValue(0.0)  # 设置初始值
            gas_input.setMaximumWidth(80)
            gas_input.setButtonSymbols(QDoubleSpinBox.NoButtons)  # 隐藏调节箭头
            gas_input.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: #2b2b2b;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: white;
                    font-size: 12px;
                }
                QDoubleSpinBox:focus {
                    border-color: #0078d4;
                }
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                    width: 0px;
                }
            """)
            gas_layout.addWidget(gas_input)
            
            # 设置按钮
            set_btn = QPushButton("设置")
            set_btn.setMaximumWidth(60)
            set_btn.setObjectName("gasSetBtn")
            # 连接按钮点击信号到槽函数
            set_btn.clicked.connect(lambda checked, gas=gas_symbol: self._on_gas_set_clicked(gas))
            gas_layout.addWidget(set_btn)
            
            # 存储控件引用
            self.gas_controls[gas_symbol] = {
                'input': gas_input,
                'button': set_btn,
                'min_val': min_val,
                'max_val': max_val
            }
            
            atmosphere_layout.addLayout(gas_layout)
        
        # 添加安全提示标签
        safety_label = QLabel("⚠️ 末端压力表工作压力0.2MPa，不可超过0.3MPa！")
        safety_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(255, 107, 107, 0.1);

                padding: 6px 8px;
                margin-top: 4px;
            }
        """)
        safety_label.setWordWrap(True)
        atmosphere_layout.addWidget(safety_label)
        
        atmosphere_group.setLayout(atmosphere_layout)
        layout.addWidget(atmosphere_group)

        # ---- 重量控制 ----
        weight_group = QGroupBox("重量控制")
        weight_layout = QGridLayout(weight_group)
        weight_layout.setSpacing(8)  # 减少间距
        
        # 天平清零按钮
        self.tare_btn = QPushButton("天平清零")
        self.tare_btn.setObjectName("tareBalanceBtn")
        weight_layout.addWidget(self.tare_btn, 0, 0)
        
        # 设置初始重量按钮
        self.set_initial_weight_btn = QPushButton("设置样品重量")
        self.set_initial_weight_btn.setObjectName("setInitialWeightBtn")
        weight_layout.addWidget(self.set_initial_weight_btn, 0, 1)
        
        weight_group.setLayout(weight_layout)
        layout.addWidget(weight_group)
        
        # 连接信号
        self.tare_btn.clicked.connect(self.tare_balance.emit)
        self.set_initial_weight_btn.clicked.connect(self.set_initial_weight.emit)

        # ---- 导出数据控制 ----
        export_group = QGroupBox("导出数据")
        export_layout = QGridLayout(export_group)
        export_layout.setSpacing(8)  # 减少间距
        
        # 保存数据按钮
        self.save_btn = QPushButton("保存数据")
        self.save_btn.setObjectName("saveDataBtn")
        export_layout.addWidget(self.save_btn, 0, 0)
        
        # 实验重置按钮
        self.reset_btn = QPushButton("实验重置")
        self.reset_btn.setObjectName("resetExperimentBtn")
        export_layout.addWidget(self.reset_btn, 0, 1)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # 连接信号
        self.save_btn.clicked.connect(self.save_data.emit)
        self.reset_btn.clicked.connect(self.reset_experiment.emit)

        layout.addStretch()
    
    def _on_gas_set_clicked(self, gas_symbol: str):
        """
        处理气体设置按钮点击事件
        
        Args:
            gas_symbol: 气体符号 (N2, CO, CO2, H2)
        """
        try:
            # 获取输入框中的流量值
            if gas_symbol not in self.gas_controls:
                return
            
            input_widget = self.gas_controls[gas_symbol]['input']
            min_val = self.gas_controls[gas_symbol]['min_val']
            max_val = self.gas_controls[gas_symbol]['max_val']
            
            # 获取当前值并保留两位小数
            flow_value = round(input_widget.value(), 2)
            
            # QDoubleSpinBox已经自动处理了范围验证，但我们可以添加额外的检查
            if flow_value < min_val or flow_value > max_val:
                QMessageBox.warning(self, "输入错误", 
                    f"{gas_symbol}流量值必须在{min_val}-{max_val} L/min范围内")
                input_widget.setFocus()
                return
            
            # 发送气体流量设置信号（确保精度为两位小数）
            self.gas_flow_set.emit(gas_symbol, flow_value)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置{gas_symbol}流量时发生错误：{str(e)}")
    
    def set_gas_flow_value(self, gas_symbol: str, flow_value: float):
        """
        设置气体流量显示值（供外部调用）
        
        Args:
            gas_symbol: 气体符号
            flow_value: 流量值
        """
        if gas_symbol in self.gas_controls:
            input_widget = self.gas_controls[gas_symbol]['input']
            min_val = self.gas_controls[gas_symbol]['min_val']
            max_val = self.gas_controls[gas_symbol]['max_val']
            
            # 确保值在有效范围内并保留两位小数
            clamped_value = round(max(min_val, min(max_val, flow_value)), 2)
            input_widget.setValue(clamped_value)
    
    def get_gas_flow_value(self, gas_symbol: str) -> float:
        """
        获取气体流量值（供外部调用）
        
        Args:
            gas_symbol: 气体符号
            
        Returns:
            float: 流量值，如果输入无效返回0.0
        """
        if gas_symbol not in self.gas_controls:
            return 0.0
        
        try:
            input_widget = self.gas_controls[gas_symbol]['input']
            return round(input_widget.value(), 2)
        except Exception:
            return 0.0
