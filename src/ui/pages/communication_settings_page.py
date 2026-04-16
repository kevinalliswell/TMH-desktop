from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QPushButton, QHBoxLayout, QMessageBox,
    QSpinBox, QLabel, QTabWidget, QToolButton,
)
from PySide6.QtCore import Qt
from src.services.comm_settings import CommSettings
from src.utils.logger import get_logger
from typing import Any, Dict


# 校验位 显示文本 <-> 配置值 映射
_PARITY_MAP: Dict[str, str] = {"N": "无校验", "E": "偶校验", "O": "奇校验"}
_PARITY_REVERSE: Dict[str, str] = {v: k for k, v in _PARITY_MAP.items()}

# 波特率选项
_BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]


class CommunicationSettings(QWidget):
    """通信参数设置页面

    所有输入控件引用保存在 ``self._widgets`` 字典中，键格式为
    ``(device_key, param_name)``，以便刷新、校验和恢复默认值。
    """

    def __init__(self, runtime=None):
        super().__init__()
        self.logger = get_logger(__name__)
        self.logger.debug("初始化通信设置页面")

        self.comm_settings = CommSettings()
        self.runtime = runtime

        # 控件引用: {(device_key, param_name): QWidget, ...}
        self._widgets: Dict[tuple, QWidget] = {}

        # 脏状态跟踪
        self._dirty = False

        self.logger.debug(f"加载的设置: {self.comm_settings.settings}")

        self._init_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _init_ui(self):
        """构建所有 UI 控件（不连接信号）"""

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 标签页
        self._tab_widget = QTabWidget()

        devices = {
            "COM_RS485_TEMP": "温度控制器",
            "COM_RS485_MFC": "气体流量计",
            "COM_RS232_Balance": "电子天平",
        }
        for device_key, title in devices.items():
            if device_key in self.comm_settings.settings:
                tab = self._create_device_tab(
                    self.comm_settings.settings[device_key], device_key
                )
                self._tab_widget.addTab(tab, title)

        sampling_tab = self._create_sampling_tab()
        self._tab_widget.addTab(sampling_tab, "采样设置")

        main_layout.addWidget(self._tab_widget)

        # 底部按钮区
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._reset_btn = QPushButton("恢复默认")
        self._reset_btn.setMinimumWidth(150)
        self._reset_btn.setMinimumHeight(40)
        button_layout.addWidget(self._reset_btn)

        self._save_btn = QPushButton("保存设置")
        self._save_btn.setMinimumWidth(150)
        self._save_btn.setMinimumHeight(40)
        button_layout.addWidget(self._save_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        main_layout.addStretch()
        self.setLayout(main_layout)

    # ------------------------------------------------------------------
    # 信号连接（集中管理）
    # ------------------------------------------------------------------
    def _connect_signals(self):
        """将所有控件信号统一连接到对应的槽函数"""

        self._save_btn.clicked.connect(self._on_save)
        self._reset_btn.clicked.connect(self._on_reset_defaults)

        # 设备串口参数
        for (device_key, param), widget in self._widgets.items():
            if param == "port":
                widget.currentTextChanged.connect(
                    lambda text, dk=device_key: self._update_setting(dk, "port", text)
                )
            elif param == "baudrate":
                widget.currentTextChanged.connect(
                    lambda text, dk=device_key: self._update_setting(dk, "baudrate", int(text))
                )
            elif param == "bytesize":
                widget.currentTextChanged.connect(
                    lambda text, dk=device_key: self._update_setting(dk, "bytesize", int(text))
                )
            elif param == "parity":
                widget.currentTextChanged.connect(
                    lambda text, dk=device_key: self._update_setting(
                        dk, "parity", _PARITY_REVERSE[text]
                    )
                )
            elif param == "stopbits":
                widget.currentTextChanged.connect(
                    lambda text, dk=device_key: self._update_setting(dk, "stopbits", float(text))
                )
            elif param == "temp_slave":
                widget.valueChanged.connect(self._update_temp_slave_address)
            elif param.startswith("mfc_slave_"):
                gas = param[len("mfc_slave_"):]
                widget.valueChanged.connect(
                    lambda v, g=gas: self._update_mfc_slave_address(g, v)
                )
            elif param.startswith("flow_scale_"):
                gas = param[len("flow_scale_"):]
                widget.valueChanged.connect(
                    lambda v, g=gas: self._update_flow_scaling(g, v / 100.0)
                )
            elif param == "sampling_interval":
                widget.valueChanged.connect(self._update_sampling_interval)

        # 串口刷新按钮
        for (device_key, param), widget in self._widgets.items():
            if param == "port_refresh":
                widget.clicked.connect(
                    lambda _, dk=device_key: self._refresh_ports(dk)
                )

    # ------------------------------------------------------------------
    # 设备标签页
    # ------------------------------------------------------------------
    def _create_device_tab(self, settings: Dict[str, Any], device_key: str) -> QWidget:
        """创建设备参数标签页并注册控件引用"""

        tab = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- 串口参数组 ---
        port_group = QGroupBox("串口参数")
        port_layout = QFormLayout()
        port_layout.setVerticalSpacing(8)
        port_layout.setHorizontalSpacing(15)

        # 串口选择 + 刷新按钮
        port_row = QHBoxLayout()
        port_combo = QComboBox()
        port_combo.setMinimumWidth(150)
        port_combo.setMinimumHeight(20)
        available_ports = self.comm_settings.get_available_ports()
        port_combo.addItems(available_ports)
        current_port = settings.get("port")
        if current_port in available_ports:
            port_combo.setCurrentText(current_port)
        elif available_ports:
            port_combo.setCurrentText(available_ports[0])
        port_row.addWidget(port_combo)

        refresh_btn = QToolButton()
        refresh_btn.setText("⟳")
        refresh_btn.setToolTip("刷新串口列表")
        refresh_btn.setMinimumSize(28, 20)
        port_row.addWidget(refresh_btn)

        self._widgets[(device_key, "port")] = port_combo
        self._widgets[(device_key, "port_refresh")] = refresh_btn
        port_layout.addRow("串口:", port_row)

        # 波特率
        baud_combo = QComboBox()
        baud_combo.setMinimumWidth(150)
        baud_combo.setMinimumHeight(20)
        baud_combo.addItems(_BAUD_RATES)
        baud_combo.setCurrentText(str(settings.get("baudrate", 9600)))
        if device_key == "COM_RS232_Balance":
            baud_combo.setEnabled(False)
            baud_combo.setToolTip("天平硬件固定 1200 波特率，不可修改")
        self._widgets[(device_key, "baudrate")] = baud_combo
        port_layout.addRow("波特率:", baud_combo)

        # 数据位
        data_combo = QComboBox()
        data_combo.setMinimumWidth(150)
        data_combo.setMinimumHeight(20)
        data_combo.addItems(["5", "6", "7", "8"])
        data_combo.setCurrentText(str(settings.get("bytesize", 8)))
        self._widgets[(device_key, "bytesize")] = data_combo
        port_layout.addRow("数据位:", data_combo)

        # 校验位
        parity_combo = QComboBox()
        parity_combo.setMinimumWidth(150)
        parity_combo.setMinimumHeight(20)
        parity_combo.addItems(_PARITY_MAP.values())
        current_parity = _PARITY_MAP.get(settings.get("parity", "N"), "无校验")
        parity_combo.setCurrentText(current_parity)
        self._widgets[(device_key, "parity")] = parity_combo
        port_layout.addRow("校验位:", parity_combo)

        # 停止位
        stop_combo = QComboBox()
        stop_combo.setMinimumWidth(150)
        stop_combo.setMinimumHeight(20)
        stop_combo.addItems(["1", "1.5", "2"])
        stop_combo.setCurrentText(str(settings.get("stopbits", 1)))
        self._widgets[(device_key, "stopbits")] = stop_combo
        port_layout.addRow("停止位:", stop_combo)

        port_group.setLayout(port_layout)
        main_layout.addWidget(port_group)

        # --- MFC 特有区域 ---
        if device_key == "COM_RS485_MFC":
            self._build_mfc_extra(main_layout)
        # --- 温控器特有区域 ---
        elif device_key == "COM_RS485_TEMP":
            self._build_temp_extra(main_layout)

        tab.setLayout(main_layout)
        return tab

    def _build_mfc_extra(self, parent_layout: QVBoxLayout):
        """构建 MFC 从机地址 + 流量缩放控件"""

        # 从机地址
        slave_group = QGroupBox("从机地址")
        slave_layout = QHBoxLayout()
        slave_layout.setSpacing(15)
        slave_layout.setContentsMargins(10, 10, 10, 10)

        slave_addresses = self.comm_settings.settings.get("SLAVE_ADDRESS_MFC", {})
        for gas, address in slave_addresses.items():
            label = QLabel(f"{gas}:")
            label.setMinimumWidth(30)
            spin = QSpinBox()
            spin.setRange(1, 247)
            spin.setValue(address)
            spin.setMinimumWidth(80)
            spin.setMinimumHeight(20)
            self._widgets[("COM_RS485_MFC", f"mfc_slave_{gas}")] = spin
            slave_layout.addWidget(label)
            slave_layout.addWidget(spin)

        slave_group.setLayout(slave_layout)
        parent_layout.addWidget(slave_group)

        # 流量缩放
        scaling_group = QGroupBox("流量缩放")
        scaling_layout = QHBoxLayout()
        scaling_layout.setSpacing(15)
        scaling_layout.setContentsMargins(10, 10, 10, 10)

        flow_scaling = self.comm_settings.settings.get("FLOW_SCALING", {})
        for gas, scale in flow_scaling.items():
            label = QLabel(f"{gas}:")
            label.setMinimumWidth(30)
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(int(scale * 100))
            spin.setSuffix("%")
            spin.setMinimumWidth(80)
            spin.setMinimumHeight(20)
            self._widgets[("COM_RS485_MFC", f"flow_scale_{gas}")] = spin
            scaling_layout.addWidget(label)
            scaling_layout.addWidget(spin)

        scaling_group.setLayout(scaling_layout)
        parent_layout.addWidget(scaling_group)

    def _build_temp_extra(self, parent_layout: QVBoxLayout):
        """构建温控器从机地址控件"""

        slave_group = QGroupBox("从机地址")
        slave_layout = QFormLayout()
        slave_layout.setVerticalSpacing(8)
        slave_layout.setHorizontalSpacing(15)

        temp_config = self.comm_settings.get_temp_config()
        slave_address = temp_config.get("slave_address", 0)

        spin = QSpinBox()
        spin.setRange(0, 247)
        spin.setValue(slave_address)
        spin.setMinimumWidth(120)
        spin.setMinimumHeight(20)
        self._widgets[("COM_RS485_TEMP", "temp_slave")] = spin
        slave_layout.addRow("温度控制器:", spin)

        slave_group.setLayout(slave_layout)
        parent_layout.addWidget(slave_group)

    # ------------------------------------------------------------------
    # 采样标签页
    # ------------------------------------------------------------------
    def _create_sampling_tab(self) -> QWidget:
        """创建采样设置标签页"""

        tab = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        sampling_group = QGroupBox("采样设置")
        sampling_layout = QFormLayout()
        sampling_layout.setVerticalSpacing(12)
        sampling_layout.setHorizontalSpacing(20)

        sampling_config = self.comm_settings.get_sampling_config()
        interval_spin = QSpinBox()
        interval_spin.setRange(1, 60)
        interval_spin.setValue(int(sampling_config.get("interval_s", 1.0)))
        interval_spin.setSuffix(" 秒")
        interval_spin.setMinimumWidth(150)
        interval_spin.setMinimumHeight(20)
        self._widgets[("SAMPLING", "sampling_interval")] = interval_spin
        sampling_layout.addRow("采样间隔:", interval_spin)

        sampling_group.setLayout(sampling_layout)
        main_layout.addWidget(sampling_group)

        info_label = QLabel("采样间隔决定了数据采集的频率，建议根据实验需求设置合适的间隔时间。")
        info_label.setWordWrap(True)
        info_label.setObjectName("infoLabel")
        main_layout.addWidget(info_label)

        main_layout.addStretch()
        tab.setLayout(main_layout)
        return tab

    # ------------------------------------------------------------------
    # 串口刷新
    # ------------------------------------------------------------------
    def _refresh_ports(self, device_key: str):
        """重新扫描可用串口并刷新对应下拉框"""

        port_combo: QComboBox = self._widgets.get((device_key, "port"))
        if not port_combo:
            return

        current_text = port_combo.currentText()
        port_combo.blockSignals(True)
        port_combo.clear()
        available_ports = self.comm_settings.get_available_ports()
        port_combo.addItems(available_ports)
        if current_text in available_ports:
            port_combo.setCurrentText(current_text)
        elif available_ports:
            port_combo.setCurrentText(available_ports[0])
        port_combo.blockSignals(False)
        self.logger.debug(f"已刷新 {device_key} 串口列表: {available_ports}")

    # ------------------------------------------------------------------
    # 设置更新方法
    # ------------------------------------------------------------------
    def _mark_dirty(self):
        """标记有未保存的修改"""
        self._dirty = True

    def _update_setting(self, device: str, key: str, value: Any) -> None:
        """更新设备串口参数"""
        try:
            self.logger.debug(f"更新设置: {device}.{key} = {value}")
            if device in self.comm_settings.settings:
                self.comm_settings.settings[device][key] = value
                self._mark_dirty()
            else:
                self.logger.warning(f"设备 {device} 不存在于配置中")
        except Exception as e:
            self.logger.error(f"更新设置失败: {str(e)}")

    def _update_mfc_slave_address(self, gas: str, address: int) -> None:
        """更新 MFC 从机地址"""
        try:
            if "SLAVE_ADDRESS_MFC" not in self.comm_settings.settings:
                self.comm_settings.settings["SLAVE_ADDRESS_MFC"] = {}
            self.comm_settings.settings["SLAVE_ADDRESS_MFC"][gas] = address
            self._mark_dirty()
            self.logger.debug(f"更新MFC从机地址: {gas} = {address}")
        except Exception as e:
            self.logger.error(f"更新MFC从机地址失败: {str(e)}")

    def _update_temp_slave_address(self, address: int) -> None:
        """更新温控仪表从机地址（同时写入嵌套和顶级配置）"""
        try:
            # 嵌套配置
            temp_config = self.comm_settings.get_temp_config()
            temp_config["slave_address"] = address

            # 顶级配置（TempClient 优先读取此值）
            if "SLAVE_ADDRESS_TEMP" not in self.comm_settings.settings:
                self.comm_settings.settings["SLAVE_ADDRESS_TEMP"] = {}
            self.comm_settings.settings["SLAVE_ADDRESS_TEMP"]["TEMP"] = address

            self._mark_dirty()
            self.logger.debug(f"更新温控仪表从机地址: {address}")
        except Exception as e:
            self.logger.error(f"更新温控仪表从机地址失败: {str(e)}")

    def _update_flow_scaling(self, gas: str, scale: float) -> None:
        """更新流量缩放"""
        try:
            if "FLOW_SCALING" not in self.comm_settings.settings:
                self.comm_settings.settings["FLOW_SCALING"] = {}
            self.comm_settings.settings["FLOW_SCALING"][gas] = scale
            self._mark_dirty()
            self.logger.debug(f"更新流量缩放: {gas} = {scale}")
        except Exception as e:
            self.logger.error(f"更新流量缩放失败: {str(e)}")

    def _update_sampling_interval(self, interval: int) -> None:
        """更新采样间隔"""
        try:
            sampling_config = self.comm_settings.get_sampling_config()
            sampling_config["interval_s"] = float(interval)
            self._mark_dirty()
            self.logger.debug(f"更新采样间隔: {interval}秒")
        except Exception as e:
            self.logger.error(f"更新采样间隔失败: {str(e)}")

    # ------------------------------------------------------------------
    # 保存 / 恢复默认
    # ------------------------------------------------------------------
    def _on_save(self) -> None:
        """保存设置到配置文件"""
        try:
            self.comm_settings.save_settings()
            self._dirty = False
            self.logger.info("通信设置已保存")
            if self.runtime:
                self.runtime.apply_comm_settings()
                QMessageBox.information(self, "提示", "设置已保存并已应用")
            else:
                QMessageBox.information(self, "提示", "设置已保存（重启后生效）")
        except Exception as e:
            self.logger.error(f"保存设置失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {str(e)}")

    def _on_reset_defaults(self) -> None:
        """恢复所有设置为默认值"""
        reply = QMessageBox.question(
            self, "确认",
            "确定要恢复所有通信参数为默认值吗？\n\n此操作不会立即保存，需手动点击「保存设置」。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        defaults = self.comm_settings.default_settings

        # 逐个控件回填默认值
        for (device_key, param), widget in self._widgets.items():
            try:
                self._apply_default_to_widget(device_key, param, widget, defaults)
            except Exception as e:
                self.logger.error(f"恢复默认值失败 ({device_key}.{param}): {e}")

        self._mark_dirty()
        self.logger.info("已恢复所有设置为默认值（尚未保存）")

    def _apply_default_to_widget(self, device_key: str, param: str,
                                  widget: QWidget, defaults: dict):
        """将单个控件恢复为默认值"""

        widget.blockSignals(True)
        try:
            if param == "port":
                dev_defaults = defaults.get(device_key, {})
                default_port = dev_defaults.get("port", "")
                if isinstance(widget, QComboBox):
                    idx = widget.findText(default_port)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    elif widget.count() > 0:
                        widget.setCurrentIndex(0)
                self._update_setting(device_key, "port", widget.currentText())
            elif param == "baudrate":
                val = str(defaults.get(device_key, {}).get("baudrate", 9600))
                widget.setCurrentText(val)
                self._update_setting(device_key, "baudrate", int(val))
            elif param == "bytesize":
                val = str(defaults.get(device_key, {}).get("bytesize", 8))
                widget.setCurrentText(val)
                self._update_setting(device_key, "bytesize", int(val))
            elif param == "parity":
                code = defaults.get(device_key, {}).get("parity", "N")
                widget.setCurrentText(_PARITY_MAP.get(code, "无校验"))
                self._update_setting(device_key, "parity", code)
            elif param == "stopbits":
                val = str(defaults.get(device_key, {}).get("stopbits", 1))
                widget.setCurrentText(val)
                self._update_setting(device_key, "stopbits", float(val))
            elif param == "temp_slave":
                default_addr = defaults.get("COM_RS485_TEMP", {}).get("slave_address", 0)
                widget.setValue(default_addr)
                self._update_temp_slave_address(default_addr)
            elif param.startswith("mfc_slave_"):
                gas = param[len("mfc_slave_"):]
                default_addr = defaults.get("SLAVE_ADDRESS_MFC", {}).get(gas, 1)
                widget.setValue(default_addr)
                self._update_mfc_slave_address(gas, default_addr)
            elif param.startswith("flow_scale_"):
                gas = param[len("flow_scale_"):]
                default_scale = defaults.get("FLOW_SCALING", {}).get(gas, 0.1)
                widget.setValue(int(default_scale * 100))
                self._update_flow_scaling(gas, default_scale)
            elif param == "sampling_interval":
                default_interval = int(defaults.get("SAMPLING", {}).get("interval_s", 1.0))
                widget.setValue(default_interval)
                self._update_sampling_interval(default_interval)
        finally:
            widget.blockSignals(False)

    # ------------------------------------------------------------------
    # 脏状态提示
    # ------------------------------------------------------------------
    def check_unsaved_changes(self) -> bool:
        """检查是否有未保存的修改，如果有则弹出提示

        Returns:
            True 表示可以继续（已保存或用户选择放弃），False 表示用户取消操作
        """
        if not self._dirty:
            return True

        reply = QMessageBox.question(
            self, "未保存的修改",
            "通信设置有未保存的修改，是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            self._on_save()
            return True
        elif reply == QMessageBox.Discard:
            self._dirty = False
            return True
        else:
            return False

    @property
    def has_unsaved_changes(self) -> bool:
        """是否存在未保存的修改"""
        return self._dirty
