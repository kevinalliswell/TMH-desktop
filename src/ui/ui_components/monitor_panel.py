# src/ui/ui_components/monitor_panel.py
from PySide6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel, QGroupBox, QHBoxLayout, QSizePolicy
from PySide6.QtCore import QTimer
from src.ui.adapters import map_frames_to_ui_snapshot
from src.utils.logger import get_logger


class MonitorPanel(QFrame):
    """
    实时监控面板
    - 主要信息：样品温度(T7-T9)、重量、失重、失重率、流量等
    - 次要信息：T1-T6温度（小字体一行显示）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = {}
        self.setObjectName("monitorPanel")
        self.setFrameStyle(QFrame.NoFrame)  # 移除边框
        
        # 字体大小配置
        self.font_sizes = {
            'normal': {
                'tempValue': 20,
                'weightValue': 16,
                'flowValue': 16,
                'mainLabel': 14
            },
            'maximized': {
                'tempValue': 40,
                'weightValue': 36,
                'flowValue': 40,
                'mainLabel': 20
            }
        }
        self.current_mode = 'normal'  # 当前模式
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)  # 减少整体间距

        # ===================== 主要监控信息 =====================
        main_group = QGroupBox("主要监控参数")
        main_layout = QGridLayout(main_group)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # 设置列的拉伸比例，让数据标签可伸缩
        # 扩展到第4行的所有列（4行×6列=24列）
        for i in range(8):  # 最多4行×2列=8列
            if i % 2 == 0:  # 标签列
                main_layout.setColumnStretch(i, 0)  # 标签列不拉伸，保持固定宽度
            else:  # 数值列
                main_layout.setColumnStretch(i, 2)  # 数值列可大幅拉伸，权重为2

        # 第1行：样品温度 (T7-T9) - 上部、中部、下部
        temp_positions = [
            ("样品温度-上(℃)", "T7", "tempValue"),
            ("样品温度-中(℃)", "T8", "tempValue"), 
            ("样品温度-下(℃)", "T9", "tempValue")
        ]
        
        for i, (label_text, temp_key, style_class) in enumerate(temp_positions):
            lbl_name = QLabel(label_text)
            lbl_value = QLabel("--")
            lbl_value.setObjectName(style_class)
            lbl_name.setObjectName("mainLabel")
            
            # 设置数据标签的尺寸策略为可扩展
            lbl_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl_name.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            
            main_layout.addWidget(lbl_name, 0, i * 2)
            main_layout.addWidget(lbl_value, 0, i * 2 + 1)
            self.labels[temp_key] = lbl_value

        # 第2行：重量相关
        weight_items = [
            ("样品重量(g)", "Balance", "weightValue"),
            ("失重(g)", "WeightLoss", "weightValue"),
            ("失重率(%)", "WeightLossRate", "weightValue")
        ]
        
        for i, (label_text, weight_key, style_class) in enumerate(weight_items):
            lbl_name = QLabel(label_text)
            lbl_value = QLabel("--")
            lbl_value.setObjectName(style_class)
            lbl_name.setObjectName("mainLabel")
            
            # 设置数据标签的尺寸策略为可扩展
            lbl_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl_name.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            
            main_layout.addWidget(lbl_name, 1, i * 2)
            main_layout.addWidget(lbl_value, 1, i * 2 + 1)
            self.labels[weight_key] = lbl_value

        # 第3行：前3个流量（N2, CO2, CO）
        flow_items_row3 = [
            ("N2流量(L/min)", "N2", "flowValue"),
            ("CO2流量(L/min)", "CO2", "flowValue"),
            ("CO流量(L/min)", "CO", "flowValue")
        ]
        
        for i, (label_text, flow_key, style_class) in enumerate(flow_items_row3):
            lbl_name = QLabel(label_text)
            lbl_value = QLabel("--")
            lbl_value.setObjectName(style_class)
            lbl_name.setObjectName("mainLabel")
            
            # 设置数据标签的尺寸策略为可扩展
            lbl_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl_name.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            
            main_layout.addWidget(lbl_name, 2, i * 2)
            main_layout.addWidget(lbl_value, 2, i * 2 + 1)
            self.labels[flow_key] = lbl_value

        # 第4行：后2个流量（H2, 总流量）
        flow_items_row4 = [
            ("H2流量(L/min)", "H2", "flowValue"),
            ("总流量(L/min)", "TotalFlow", "flowValue")
        ]
        
        for i, (label_text, flow_key, style_class) in enumerate(flow_items_row4):
            lbl_name = QLabel(label_text)
            lbl_value = QLabel("--")
            lbl_value.setObjectName(style_class)
            lbl_name.setObjectName("mainLabel")
            
            # 设置数据标签的尺寸策略为可扩展
            lbl_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl_name.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            
            main_layout.addWidget(lbl_name, 3, i * 2)
            main_layout.addWidget(lbl_value, 3, i * 2 + 1)
            self.labels[flow_key] = lbl_value

        # 设置主要监控信息的垂直拉伸比例为70%
        layout.addWidget(main_group, 7)

        # ===================== 次要温度信息 (T1-T6) =====================
        minor_temp_group = QGroupBox("其他温度 (°C)")
        minor_temp_group.setMaximumHeight(60)  # 限制次要信息的最大高度
        minor_temp_layout = QHBoxLayout(minor_temp_group)
        minor_temp_layout.setContentsMargins(8, 4, 8, 4)
        minor_temp_layout.setSpacing(4)
        
        # 定义新的标签名称
        minor_temp_labels = ["PV1", "SV1", "PV2", "SV2", "PV3", "SV3"]
        for i, name in enumerate(minor_temp_labels):
            lbl_name = QLabel(f"{name}:")
            lbl_value = QLabel("--")
            lbl_value.setObjectName("minorTempValue")
            lbl_name.setObjectName("minorTempLabel")
            
            minor_temp_layout.addWidget(lbl_name)
            minor_temp_layout.addWidget(lbl_value)
            self.labels[name] = lbl_value
            
            # 在每个温度值后添加少量间距，但最后一个不加
            if i < len(minor_temp_labels) - 1:
                minor_temp_layout.addSpacing(8)
        
        minor_temp_layout.addStretch()
        # 设置次要温度信息的垂直拉伸比例为30%
        layout.addWidget(minor_temp_group, 3)

    # ===================== 字体大小调整函数 =====================
    def adjust_font_size(self, is_maximized=False):
        """
        根据窗体状态调整字体大小
        
        Args:
            is_maximized (bool): True表示窗体最大化，False表示正常大小
        """
        mode = 'maximized' if is_maximized else 'normal'
        
        if mode == self.current_mode:
            return  # 模式未改变，无需调整
            
        self.current_mode = mode
        font_config = self.font_sizes[mode]
        
        # print(f"[DEBUG] 调整字体大小到 {mode} 模式: {font_config}")  # 调试信息
        
        # 通过设置样式表来覆盖CSS，确保字体大小生效
        style_updates = []
        
        # 温度值样式
        style_updates.append(f"""
        QLabel#tempValue {{
            font-size: {font_config['tempValue']}px !important;
        }}
        """)
        
        # 重量值样式
        style_updates.append(f"""
        QLabel#weightValue {{
            font-size: {font_config['weightValue']}px !important;
        }}
        """)
        
        # 流量值样式
        style_updates.append(f"""
        QLabel#flowValue {{
            font-size: {font_config['flowValue']}px !important;
        }}
        """)
        
        # 主标签样式
        style_updates.append(f"""
        QLabel#mainLabel {{
            font-size: {font_config['mainLabel']}px !important;
        }}
        """)
        
        # 合并所有样式并应用
        combined_style = ''.join(style_updates)
        self.setStyleSheet(combined_style)
        
        # 强制刷新界面
        self.update()
        
        get_logger(__name__).debug(f"字体样式已应用: {len(style_updates)} 个规则")
    
    def set_window_maximized_state(self, is_maximized):
        """
        外部调用接口，设置窗体最大化状态
        
        Args:
            is_maximized (bool): 窗体是否最大化
        """
        # print(f"[DEBUG] 收到窗体状态变化通知: {'最大化' if is_maximized else '正常'}")
        # 延迟调整字体大小，确保布局已经完成
        QTimer.singleShot(100, lambda: self.adjust_font_size(is_maximized))
    
    def test_font_size_toggle(self):
        """
        测试方法：手动切换字体大小状态
        """
        current_maximized = self.current_mode == 'maximized'
        new_state = not current_maximized
        # print(f"[TEST] 切换字体状态: {self.current_mode} -> {'maximized' if new_state else 'normal'}")
        self.adjust_font_size(new_state)

    # ===================== 更新函数 =====================
    def update_monitor(self, frames: dict, initial_weight: float = 0.0):
        """
        更新监控数据（仅使用标准化 frames）
        """
        snapshot = map_frames_to_ui_snapshot(frames)

        # 温度 - 主要温度 (T7-T9)
        temps = snapshot.temperatures
        if temps:
            for name, val in temps.items():
                if name in self.labels:
                    if val is not None:
                        if name in ["T7", "T8", "T9"]:  # 主要温度
                            self.labels[name].setText(f"{val:.1f}")
                        else:  # 次要温度
                            self.labels[name].setText(f"{val:.1f}")
                    else:
                        self.labels[name].setText("--")
        else:
            # 当没有温度数据时，设置所有温度标签为 "--"
            temp_labels = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
            for name in temp_labels:
                if name in self.labels:
                    self.labels[name].setText("--")

        # 流量信息
        flows = snapshot.flows
        if flows:
            for gas, val in flows.items():
                if gas in self.labels:
                    if val is not None:
                        flow_val = val
                        self.labels[gas].setText(f"{flow_val:.2f}")
                    else:
                        self.labels[gas].setText("--")
            
            # 更新总流量
            if "TotalFlow" in self.labels:
                self.labels["TotalFlow"].setText(f"{snapshot.total_flow:.2f}")
        else:
            # 当没有流量数据时，设置所有气体标签为 "--"
            gas_labels = ["N2", "CO", "CO2", "H2", "TotalFlow"]
            for name in gas_labels:
                if name in self.labels:
                    self.labels[name].setText("--")

        # 重量相关
        if snapshot.weight is None:
            # 当没有重量数据时显示 "--"
            self.labels["Balance"].setText("--")
            self.labels["WeightLoss"].setText("--")
            self.labels["WeightLossRate"].setText("--")
            return

        w = snapshot.weight
        self.labels["Balance"].setText(f"{w:.3f}")
        if initial_weight > 0:
            weight_loss = initial_weight - w
            weight_loss_rate = (weight_loss / initial_weight) * 100
            self.labels["WeightLoss"].setText(f"{weight_loss:.3f}")
            self.labels["WeightLossRate"].setText(f"{weight_loss_rate:.2f}%")
        else:
            self.labels["WeightLoss"].setText("--")
            self.labels["WeightLossRate"].setText("--")
