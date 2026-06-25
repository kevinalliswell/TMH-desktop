"""
实验模式设置页面
用于查看和编辑实验模式配置
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QComboBox, QTextEdit, QGroupBox, QMessageBox,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QLineEdit, QDoubleSpinBox, QCheckBox,
                               QSplitter, QListWidget, QListWidgetItem,
                               QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QInputDialog)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
import copy
from datetime import datetime

from src.services.experiment_modes import ExperimentModeManager


class StageEditDialog(QDialog):
    """阶段编辑对话框"""
    
    def __init__(self, stage_data=None, parent=None, gas_safety_limits=None):
        super().__init__(parent)
        self.stage_data = stage_data or {}
        # 可燃气体（H2/CO）流量安全上限，驱动输入框上界；缺省 5.0 L/min
        self.gas_safety_limits = gas_safety_limits or {"H2": 5.0, "CO": 5.0}
        self.setWindowTitle("编辑实验阶段")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_stage_data()
        
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        
        # 阶段基本信息
        basic_group = QGroupBox("阶段基本信息")
        basic_layout = QFormLayout()
        
        self.stage_name_combo = QComboBox()
        self.stage_name_combo.addItems(["HEATING", "STABILIZING", "REDUCING", "COOLING"])
        basic_layout.addRow("阶段名称:", self.stage_name_combo)
        
        self.description_edit = QLineEdit()
        basic_layout.addRow("描述:", self.description_edit)
        
        self.target_temp_spin = QDoubleSpinBox()
        self.target_temp_spin.setRange(25, 1200)
        self.target_temp_spin.setSuffix(" ℃")
        basic_layout.addRow("目标温度:", self.target_temp_spin)
        
        self.temp_tolerance_spin = QDoubleSpinBox()
        self.temp_tolerance_spin.setRange(0, 50)
        self.temp_tolerance_spin.setSuffix(" ℃")
        basic_layout.addRow("温度容差:", self.temp_tolerance_spin)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 1440)
        self.duration_spin.setSuffix(" min")
        basic_layout.addRow("持续时间:", self.duration_spin)
        
        self.heating_rate_spin = QDoubleSpinBox()
        self.heating_rate_spin.setRange(-50, 50)
        self.heating_rate_spin.setSuffix(" ℃/min")
        basic_layout.addRow("升温速率:", self.heating_rate_spin)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 气体设置
        gas_group = QGroupBox("气体设置")
        gas_layout = QFormLayout()
        
        self.co_flow_spin = QDoubleSpinBox()
        self.co_flow_spin.setRange(0, float(self.gas_safety_limits.get("CO", 5.0)))
        self.co_flow_spin.setSuffix(" L/min")
        gas_layout.addRow("CO流量:", self.co_flow_spin)
        
        self.co2_flow_spin = QDoubleSpinBox()
        self.co2_flow_spin.setRange(0, 15)
        self.co2_flow_spin.setSuffix(" L/min")
        gas_layout.addRow("CO₂流量:", self.co2_flow_spin)
        
        self.n2_flow_spin = QDoubleSpinBox()
        self.n2_flow_spin.setRange(0, 15)
        self.n2_flow_spin.setSuffix(" L/min")
        gas_layout.addRow("N₂流量:", self.n2_flow_spin)
        
        self.h2_flow_spin = QDoubleSpinBox()
        self.h2_flow_spin.setRange(0, float(self.gas_safety_limits.get("H2", 5.0)))
        self.h2_flow_spin.setSuffix(" L/min")
        gas_layout.addRow("H₂流量:", self.h2_flow_spin)
        
        gas_group.setLayout(gas_layout)
        layout.addWidget(gas_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def load_stage_data(self):
        """加载阶段数据"""
        if self.stage_data:
            self.stage_name_combo.setCurrentText(self.stage_data.get("stage_name", "HEATING"))
            self.description_edit.setText(self.stage_data.get("description", ""))
            self.target_temp_spin.setValue(self.stage_data.get("target_temp", 25.0))
            self.temp_tolerance_spin.setValue(self.stage_data.get("temp_tolerance", 5.0))
            self.duration_spin.setValue(self.stage_data.get("duration", 0.0))
            self.heating_rate_spin.setValue(self.stage_data.get("heating_rate", 0.0))
            
            gas_settings = self.stage_data.get("gas_settings", {})
            self.co_flow_spin.setValue(gas_settings.get("CO", 0.0))
            self.co2_flow_spin.setValue(gas_settings.get("CO2", 0.0))
            self.n2_flow_spin.setValue(gas_settings.get("N2", 0.0))
            self.h2_flow_spin.setValue(gas_settings.get("H2", 0.0))
    
    def get_stage_data(self):
        """获取阶段数据"""
        return {
            "stage_name": self.stage_name_combo.currentText(),
            "description": self.description_edit.text(),
            "target_temp": self.target_temp_spin.value(),
            "temp_tolerance": self.temp_tolerance_spin.value(),
            "duration": self.duration_spin.value(),
            "heating_rate": self.heating_rate_spin.value(),
            "gas_settings": {
                "CO": self.co_flow_spin.value(),
                "CO2": self.co2_flow_spin.value(),
                "N2": self.n2_flow_spin.value(),
                "H2": self.h2_flow_spin.value(),
                "total_flow": (self.co_flow_spin.value() + self.co2_flow_spin.value() + 
                             self.n2_flow_spin.value() + self.h2_flow_spin.value())
            }
        }


class ExperimentModeSettingsPage(QWidget):
    """实验模式设置页面"""
    
    # 自定义信号：通知其他组件实验模式发生变化
    mode_created = Signal(str, dict)   # (mode_id, mode_data)
    mode_updated = Signal(str, dict)   # (mode_id, mode_data)
    mode_deleted = Signal(str)         # (mode_id,)
    
    def __init__(self, parent=None, mode_manager=None, gas_safety_limits=None):
        super().__init__(parent)
        # 可燃气体（H2/CO）流量安全上限，传递给阶段编辑对话框；缺省 5.0 L/min
        self.gas_safety_limits = gas_safety_limits or {"H2": 5.0, "CO": 5.0}
        self.setWindowTitle("实验模式设置")
        
        # 实验模式管理器
        self.mode_manager = mode_manager or ExperimentModeManager()
        
        # 当前选中的实验模式
        self.current_mode = None
        self.current_mode_type = None  # 'standard' 或 'custom'
        
        # 初始化UI
        self.init_ui()
        
        # 加载实验模式数据
        self.load_experiment_modes()
    
    def init_ui(self):
        """初始化用户界面"""
        # 设置对象名称以便QSS样式应用
        self.setObjectName("experimentModeSettings")
        
        # 主布局 - 使用QSplitter实现弹性可调节宽度
        main_layout = QHBoxLayout()
        
        # 创建水平分割器
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：实验模式列表
        left_widget = self.create_mode_list_widget()
        self.splitter.addWidget(left_widget)
        
        # 右侧：实验模式详情
        right_widget = self.create_mode_detail_widget()
        self.splitter.addWidget(right_widget)
        
        # 设置初始比例 (左侧30%, 右侧70%)
        self.splitter.setSizes([300, 700])
        
        # 设置最小宽度
        self.splitter.setMinimumSize(800, 600)
        self.splitter.widget(0).setMinimumWidth(250)  # 左侧最小宽度
        self.splitter.widget(1).setMinimumWidth(400)  # 右侧最小宽度
        
        # 设置分割器样式
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #555555;
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: #b19cd9;
            }
            QSplitter::handle:pressed {
                background-color: #9d7bd8;
            }
        """)
        
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)
    
    def create_mode_list_widget(self):
        """创建实验模式列表组件"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 合并的实验模式列表
        modes_group = QGroupBox("实验模式")
        modes_layout = QVBoxLayout()
        
        self.modes_list = QListWidget()
        self.modes_list.itemClicked.connect(self.on_mode_selected)
        modes_layout.addWidget(self.modes_list)
        
        # 操作按钮 - 并排显示
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()  # 左侧弹性空间

        self.copy_standard_btn = QPushButton("复制")
        self.copy_standard_btn.setToolTip("选中标准模式进行复制操作")
        self.copy_standard_btn.setObjectName("addBtn")
        self.copy_standard_btn.clicked.connect(self.copy_standard_mode)
        self.copy_standard_btn.setEnabled(False)
        btn_layout.addWidget(self.copy_standard_btn)

        self.add_custom_btn = QPushButton("添加")
        self.add_custom_btn.setToolTip("添加自定义模式")
        self.add_custom_btn.setObjectName("addBtn")
        self.add_custom_btn.clicked.connect(self.add_custom_mode)
        btn_layout.addWidget(self.add_custom_btn)

        self.delete_custom_btn = QPushButton("删除")
        self.delete_custom_btn.setToolTip("删除选中模式")
        self.delete_custom_btn.setObjectName("deleteBtn")
        self.delete_custom_btn.clicked.connect(self.delete_custom_mode)
        self.delete_custom_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_custom_btn)

        btn_layout.addStretch()  # 右侧弹性空间

        modes_layout.addLayout(btn_layout)
        modes_group.setLayout(modes_layout)
        layout.addWidget(modes_group)
        
        widget.setLayout(layout)
        return widget
    
    def create_mode_detail_widget(self):
        """创建实验模式详情组件"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 基本信息
        self.basic_info_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)
        basic_layout.addRow("名称:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setReadOnly(True)
        self.description_edit.setMaximumHeight(80)
        basic_layout.addRow("描述:", self.description_edit)
        
        self.category_edit = QLineEdit()
        self.category_edit.setReadOnly(True)
        basic_layout.addRow("类别:", self.category_edit)
        
        self.enabled_checkbox = QCheckBox("启用")
        self.enabled_checkbox.setEnabled(False)
        basic_layout.addRow("状态:", self.enabled_checkbox)
        
        self.basic_info_group.setLayout(basic_layout)
        layout.addWidget(self.basic_info_group)
        
        # 阶段列表
        self.stages_group = QGroupBox("实验阶段")
        stages_layout = QVBoxLayout()
        
        self.stages_table = QTableWidget()
        self.stages_table.setColumnCount(7)
        self.stages_table.setHorizontalHeaderLabels([
            "阶段", "描述", "温度(℃)", "时间(min)", "升温速率(℃/min)", "气体组成(L/min)", "操作"
        ])
        
        # 设置表格属性
        header = self.stages_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.stages_table.setAlternatingRowColors(True)
        self.stages_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stages_table.setMinimumHeight(200)
        self.stages_table.itemSelectionChanged.connect(self._on_stage_selection_changed)
        
        stages_layout.addWidget(self.stages_table)
        
        # 阶段操作按钮 - 四个按钮水平居中布置
        stages_btn_layout = QHBoxLayout()
        stages_btn_layout.addStretch(1)

        self.add_stage_btn = QPushButton("添加阶段")
        self.add_stage_btn.setObjectName("addBtn")
        self.add_stage_btn.clicked.connect(self.add_stage)
        self.add_stage_btn.setEnabled(False)
        stages_btn_layout.addWidget(self.add_stage_btn)

        self.edit_stage_btn = QPushButton("编辑阶段")
        self.edit_stage_btn.clicked.connect(self.edit_stage)
        self.edit_stage_btn.setEnabled(False)
        stages_btn_layout.addWidget(self.edit_stage_btn)

        self.delete_stage_btn = QPushButton("删除阶段")
        self.delete_stage_btn.setObjectName("deleteBtn")
        self.delete_stage_btn.clicked.connect(self.delete_stage)
        self.delete_stage_btn.setEnabled(False)
        stages_btn_layout.addWidget(self.delete_stage_btn)

        # 保存按钮也加入到同一行
        self.save_btn = QPushButton("保存修改")
        self.save_btn.clicked.connect(self.save_mode)
        self.save_btn.setEnabled(False)
        stages_btn_layout.addWidget(self.save_btn)

        stages_btn_layout.addStretch(1)

        stages_layout.addLayout(stages_btn_layout)

        self.stages_group.setLayout(stages_layout)
        layout.addWidget(self.stages_group)
        
        # 状态消息标签（替代频繁弹窗）
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusMessage")
        self._status_label.setStyleSheet("""
            QLabel#statusMessage {
                color: #4CAF50;
                font-size: 10pt;
                padding: 4px 8px;
            }
        """)
        layout.addWidget(self._status_label)
        
        widget.setLayout(layout)
        return widget
    
    def load_experiment_modes(self):
        """加载实验模式数据"""
        # 清空合并列表
        self.modes_list.clear()
        
        # 加载标准实验模式
        standard_modes = self.mode_manager.get_standard_modes()
        for mode_id, mode_data in standard_modes.items():
            item = QListWidgetItem(f"[标准] {mode_data['name']}")
            item.setData(Qt.UserRole, {'id': mode_id, 'type': 'standard'})
            item.setToolTip(f"标准实验模式 - {mode_data['description']}")
            self.modes_list.addItem(item)
        
        # 加载自定义实验模式
        custom_modes = self.mode_manager.get_custom_modes()
        for mode_id, mode_data in custom_modes.items():
            item = QListWidgetItem(f"[自定义] {mode_data['name']}")
            item.setData(Qt.UserRole, {'id': mode_id, 'type': 'custom'})
            item.setToolTip(f"自定义实验模式 - {mode_data['description']}")
            self.modes_list.addItem(item)
    
    def on_mode_selected(self, item):
        """模式被选中"""
        mode_data = item.data(Qt.UserRole)
        self.current_mode = mode_data['id']
        self.current_mode_type = mode_data['type']
        self.load_mode_details()
        
        # 根据模式类型设置按钮状态
        if self.current_mode_type == 'standard':
            # 标准模式：禁用编辑功能，启用复制功能
            self.set_edit_mode(False)
            self.copy_standard_btn.setEnabled(True)
            self.delete_custom_btn.setEnabled(False)
        else:
            # 自定义模式：启用编辑功能，禁用复制功能
            self.set_edit_mode(True)
            self.copy_standard_btn.setEnabled(False)
            self.delete_custom_btn.setEnabled(True)
    
    def set_edit_mode(self, enabled):
        """设置编辑模式"""
        self._is_edit_mode = enabled
        
        # 基本信息编辑
        self.name_edit.setReadOnly(not enabled)
        self.description_edit.setReadOnly(not enabled)
        self.category_edit.setReadOnly(not enabled)
        self.enabled_checkbox.setEnabled(enabled)
        
        # 添加阶段按钮始终跟随编辑模式
        self.add_stage_btn.setEnabled(enabled)
        
        # 编辑/删除阶段按钮仅在编辑模式且有行被选中时启用
        has_selection = self.stages_table.currentRow() >= 0
        self.edit_stage_btn.setEnabled(enabled and has_selection)
        self.delete_stage_btn.setEnabled(enabled and has_selection)
        
        # 保存按钮
        self.save_btn.setEnabled(enabled)
    
    def _on_stage_selection_changed(self):
        """阶段表格选中行变化时更新按钮状态"""
        if not getattr(self, '_is_edit_mode', False):
            return
        has_selection = self.stages_table.currentRow() >= 0
        self.edit_stage_btn.setEnabled(has_selection)
        self.delete_stage_btn.setEnabled(has_selection)
    
    def load_mode_details(self):
        """加载模式详情"""
        if not self.current_mode:
            return
        
        # 获取模式数据
        if self.current_mode_type == 'standard':
            mode_data = self.mode_manager.get_standard_mode(self.current_mode)
        else:
            mode_data = self.mode_manager.get_custom_mode(self.current_mode)
        
        if not mode_data:
            return
        
        # 更新基本信息
        self.name_edit.setText(mode_data['name'])
        self.description_edit.setPlainText(mode_data['description'])
        self.category_edit.setText(mode_data['category'])
        self.enabled_checkbox.setChecked(mode_data.get('enabled', True))
        
        # 更新阶段列表
        self.update_stages_table(mode_data.get('stages', []))
    
    def update_stages_table(self, stages):
        """更新阶段表格"""
        self.stages_table.setRowCount(len(stages))
        
        for row, stage in enumerate(stages):
            # 阶段名称
            stage_item = QTableWidgetItem(stage['stage_name'])
            stage_item.setTextAlignment(Qt.AlignCenter)
            self.stages_table.setItem(row, 0, stage_item)
            
            # 描述
            desc_item = QTableWidgetItem(stage['description'])
            self.stages_table.setItem(row, 1, desc_item)
            
            # 温度
            temp_text = f"{stage['target_temp']:.0f}±{stage['temp_tolerance']:.0f}"
            temp_item = QTableWidgetItem(temp_text)
            temp_item.setTextAlignment(Qt.AlignCenter)
            self.stages_table.setItem(row, 2, temp_item)
            
            # 时间
            time_text = f"{stage['duration']:.0f}" if stage['duration'] > 0 else "动态"
            time_item = QTableWidgetItem(time_text)
            time_item.setTextAlignment(Qt.AlignCenter)
            self.stages_table.setItem(row, 3, time_item)
            
            # 升温速率
            rate_text = f"{stage['heating_rate']:.1f}"
            rate_item = QTableWidgetItem(rate_text)
            rate_item.setTextAlignment(Qt.AlignCenter)
            self.stages_table.setItem(row, 4, rate_item)
            
            # 气体组成
            gas_settings = stage.get('gas_settings', {})
            gas_parts = []
            if gas_settings.get('CO', 0) > 0:
                gas_parts.append(f"{gas_settings['CO']:.1f}CO")
            if gas_settings.get('CO2', 0) > 0:
                gas_parts.append(f"{gas_settings['CO2']:.1f}CO₂")
            if gas_settings.get('N2', 0) > 0:
                gas_parts.append(f"{gas_settings['N2']:.1f}N₂")
            if gas_settings.get('H2', 0) > 0:
                gas_parts.append(f"{gas_settings['H2']:.1f}H₂")
            
            gas_text = " + ".join(gas_parts) if gas_parts else "无"
            gas_item = QTableWidgetItem(gas_text)
            gas_item.setTextAlignment(Qt.AlignCenter)
            self.stages_table.setItem(row, 5, gas_item)
            
            # 操作按钮
            if self.current_mode_type == 'custom':
                edit_btn = QPushButton("编辑")
                edit_btn.setFixedSize(50, 25)  # 设置固定小尺寸
                edit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #b19cd9;
                        color: #ffffff;
                        border: none;
                        border-radius: 3px;
                        font-size: 9pt;
                        font-weight: bold;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #9d7bd8;
                    }
                    QPushButton:pressed {
                        background-color: #8a6bc7;
                    }
                """)
                edit_btn.clicked.connect(lambda checked, r=row: self.edit_stage_at_row(r))
                self.stages_table.setCellWidget(row, 6, edit_btn)
            else:
                # 标准模式显示"只读"
                readonly_item = QTableWidgetItem("只读")
                readonly_item.setTextAlignment(Qt.AlignCenter)
                readonly_item.setBackground(QColor("#666666"))
                self.stages_table.setItem(row, 6, readonly_item)
        
        # 调整行高
        self.stages_table.resizeRowsToContents()
    
    def add_custom_mode(self):
        """添加自定义模式"""
        name, ok = QInputDialog.getText(self, "添加自定义模式", "请输入模式名称:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # 检查名称是否与已有模式重复
        existing_custom = self.mode_manager.get_custom_modes()
        existing_standard = self.mode_manager.get_standard_modes()
        all_names = ([m['name'] for m in existing_custom.values()] +
                     [m['name'] for m in existing_standard.values()])
        if name in all_names:
            QMessageBox.warning(self, "错误", f"名称 '{name}' 已存在，请使用其他名称！")
            return
        
        # 生成模式ID并检查ID是否重复
        mode_id = f"CUSTOM_{name.upper().replace(' ', '_')}"
        if mode_id in existing_custom:
            mode_id = f"{mode_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建新的自定义模式
        new_mode = {
            "name": name,
            "description": "用户自定义实验模式",
            "category": "custom",
            "enabled": True,
            "created_by": "user",
            "created_time": datetime.now().isoformat(),
            "stages": []
        }
        
        # 添加到模式管理器
        if self.mode_manager.add_custom_mode(mode_id, new_mode):
            self.mode_created.emit(mode_id, new_mode)
            # 刷新列表
            self.load_experiment_modes()
            # 选中新添加的模式
            for i in range(self.modes_list.count()):
                item = self.modes_list.item(i)
                if item.data(Qt.UserRole)['id'] == mode_id:
                    self.modes_list.setCurrentItem(item)
                    self.on_mode_selected(item)
                    break
        else:
            QMessageBox.warning(self, "错误", "添加自定义模式失败！")
    
    def delete_custom_mode(self):
        """删除自定义模式"""
        if not self.current_mode or self.current_mode_type != 'custom':
            return
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除自定义模式 '{self.current_mode}' 吗？\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_mode_id = self.current_mode
            if self.mode_manager.delete_custom_mode(deleted_mode_id):
                self.mode_deleted.emit(deleted_mode_id)
                self.load_experiment_modes()
                self.clear_mode_details()
                self._show_status_message("自定义模式已删除")
            else:
                QMessageBox.warning(self, "错误", "删除自定义模式失败！")
    
    def clear_mode_details(self):
        """清空模式详情"""
        self.name_edit.clear()
        self.description_edit.clear()
        self.category_edit.clear()
        self.enabled_checkbox.setChecked(False)
        self.stages_table.setRowCount(0)
        self.current_mode = None
        self.current_mode_type = None
        self.set_edit_mode(False)
        self.delete_custom_btn.setEnabled(False)
    
    def _show_status_message(self, message, timeout_ms=3000):
        """在状态标签中显示临时消息，替代频繁弹窗"""
        self._status_label.setText(message)
        QTimer.singleShot(timeout_ms, lambda: self._status_label.setText(""))
    
    def add_stage(self):
        """添加阶段"""
        if self.current_mode_type != 'custom':
            return
        
        dialog = StageEditDialog(parent=self, gas_safety_limits=self.gas_safety_limits)
        if dialog.exec() == QDialog.Accepted:
            stage_data = dialog.get_stage_data()
            
            # 获取当前模式数据
            mode_data = self.mode_manager.get_custom_mode(self.current_mode)
            if not mode_data:
                return
            
            # 添加阶段
            if 'stages' not in mode_data:
                mode_data['stages'] = []
            mode_data['stages'].append(stage_data)
            
            # 更新模式
            if self.mode_manager.update_custom_mode(self.current_mode, mode_data):
                self.mode_updated.emit(self.current_mode, mode_data)
                self.load_mode_details()
                self._show_status_message("阶段添加成功")
            else:
                QMessageBox.warning(self, "错误", "添加阶段失败！")
    
    def edit_stage(self):
        """编辑阶段"""
        if self.current_mode_type != 'custom':
            return
        
        current_row = self.stages_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要编辑的阶段！")
            return
        
        # 获取当前阶段数据
        stage_data = self.get_stage_data_at_row(current_row)
        if not stage_data:
            return
        
        dialog = StageEditDialog(stage_data, parent=self, gas_safety_limits=self.gas_safety_limits)
        if dialog.exec() == QDialog.Accepted:
            new_stage_data = dialog.get_stage_data()
            
            # 获取当前模式数据
            mode_data = self.mode_manager.get_custom_mode(self.current_mode)
            if not mode_data:
                return
            
            # 更新阶段数据
            if 'stages' in mode_data and 0 <= current_row < len(mode_data['stages']):
                mode_data['stages'][current_row] = new_stage_data
                
                # 更新模式
                if self.mode_manager.update_custom_mode(self.current_mode, mode_data):
                    self.mode_updated.emit(self.current_mode, mode_data)
                    self.load_mode_details()
                    self._show_status_message("阶段编辑成功")
                else:
                    QMessageBox.warning(self, "错误", "编辑阶段失败！")
    
    def edit_stage_at_row(self, row):
        """编辑指定行的阶段"""
        self.stages_table.selectRow(row)
        self.edit_stage()
    
    def delete_stage(self):
        """删除阶段"""
        if self.current_mode_type != 'custom':
            return
        
        current_row = self.stages_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请选择要删除的阶段！")
            return
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            "确定要删除选中的阶段吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 获取当前模式数据
            mode_data = self.mode_manager.get_custom_mode(self.current_mode)
            if not mode_data:
                return
            
            # 删除阶段
            if 'stages' in mode_data and 0 <= current_row < len(mode_data['stages']):
                del mode_data['stages'][current_row]
                
                # 更新模式
                if self.mode_manager.update_custom_mode(self.current_mode, mode_data):
                    self.mode_updated.emit(self.current_mode, mode_data)
                    self.load_mode_details()
                    self._show_status_message("阶段删除成功")
                else:
                    QMessageBox.warning(self, "错误", "删除阶段失败！")
    
    def get_stage_data_at_row(self, row):
        """获取指定行的阶段数据"""
        if not self.current_mode or self.current_mode_type != 'custom':
            return {}
        
        mode_data = self.mode_manager.get_custom_mode(self.current_mode)
        if not mode_data or 'stages' not in mode_data:
            return {}
        
        stages = mode_data['stages']
        if 0 <= row < len(stages):
            return stages[row]
        
        return {}
    
    def save_mode(self):
        """保存模式"""
        if self.current_mode_type != 'custom':
            return
        
        # 获取当前模式数据
        mode_data = self.mode_manager.get_custom_mode(self.current_mode)
        if not mode_data:
            return
        
        # 更新基本信息
        mode_data['name'] = self.name_edit.text()
        mode_data['description'] = self.description_edit.toPlainText()
        mode_data['category'] = self.category_edit.text()
        mode_data['enabled'] = self.enabled_checkbox.isChecked()
        
        # 保存模式
        if self.mode_manager.update_custom_mode(self.current_mode, mode_data):
            self.mode_updated.emit(self.current_mode, mode_data)
            self._show_status_message("模式保存成功")
            # 刷新列表
            self.load_experiment_modes()
        else:
            QMessageBox.warning(self, "错误", "保存模式失败！")
    
    def copy_standard_mode(self):
        """复制标准模式为自定义模式"""
        if not self.current_mode or self.current_mode_type != 'standard':
            return
        
        # 获取标准模式数据
        standard_mode_data = self.mode_manager.get_standard_mode(self.current_mode)
        if not standard_mode_data:
            QMessageBox.warning(self, "错误", "无法获取标准模式数据！")
            return
        
        original_name = standard_mode_data['name']
        suggested_name = f"自定义_{original_name}"
        
        name, ok = QInputDialog.getText(
            self, 
            "复制标准模式", 
            f"请输入新自定义模式的名称:\n\n原模式: {original_name}",
            text=suggested_name
        )
        
        if not ok or not name.strip():
            return
        
        # 检查名称是否已存在
        existing_modes = self.mode_manager.get_custom_modes()
        if any(mode['name'] == name for mode in existing_modes.values()):
            QMessageBox.warning(self, "错误", f"名称 '{name}' 已存在，请使用其他名称！")
            return
        
        # 创建新的自定义模式数据（深拷贝以避免共享嵌套对象）
        new_mode_data = copy.deepcopy(standard_mode_data)
        new_mode_data.update({
            'name': name,
            'description': f"从 {original_name} 复制的自定义实验模式",
            'category': 'custom',
            'created_by': 'user',
            'created_time': datetime.now().isoformat(),
            'copied_from': self.current_mode
        })
        
        # 生成新的模式ID
        mode_id = f"CUSTOM_COPIED_{self.current_mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 添加到模式管理器
        if self.mode_manager.add_custom_mode(mode_id, new_mode_data):
            self.mode_created.emit(mode_id, new_mode_data)
            self._show_status_message(f"已复制为自定义模式 '{name}'")
            
            # 刷新列表
            self.load_experiment_modes()
            
            # 自动选中新复制的模式
            for i in range(self.modes_list.count()):
                item = self.modes_list.item(i)
                if item.data(Qt.UserRole)['id'] == mode_id:
                    self.modes_list.setCurrentItem(item)
                    self.on_mode_selected(item)
                    break
        else:
            QMessageBox.warning(self, "错误", "复制标准模式失败！")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    page = ExperimentModeSettingsPage()
    page.show()
    sys.exit(app.exec())
