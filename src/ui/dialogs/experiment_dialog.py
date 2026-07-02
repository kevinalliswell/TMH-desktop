from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QComboBox, QPushButton, QLabel,
                               QSpinBox, QDoubleSpinBox, QGroupBox, QTextEdit,
                               QMessageBox, QDateTimeEdit)
from PySide6.QtCore import Qt, QDateTime
import json
import os

from src.utils.path_manager import PathManager
from src.services.experiment_modes import ExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager


class ExperimentDialog(QDialog):
    """实验参数设置对话框"""
    exp_config = PathManager.get_config_path('exp_settings.config')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实验参数设置")
        self.setModal(True)  # 设置为模态对话框
        self.experiment_mode_manager = ExperimentModeManager()
        self.experiment_type_manager = ExperimentTypeManager()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()

        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()

        # 项目名称
        self.project_name = QLineEdit()
        basic_layout.addRow("项目名称:", self.project_name)

        # 样品名称
        self.sample_name = QLineEdit()
        basic_layout.addRow("样品名称:", self.sample_name)

        # 样品编号
        sample_id_layout = QHBoxLayout()
        self.sample_id = QLineEdit()
        generate_btn = QPushButton("生成编号")
        generate_btn.clicked.connect(self.generate_sample_id)
        sample_id_layout.addWidget(self.sample_id)
        sample_id_layout.addWidget(generate_btn)
        basic_layout.addRow("样品编号:", sample_id_layout)

        # 实验类型
        self.exp_type = QComboBox()
        self.load_experiment_types()
        basic_layout.addRow("实验类型:", self.exp_type)

        # 样品初重
        self.sample_weight = QDoubleSpinBox()
        self.sample_weight.setRange(0, 1000)  # 0-1000g
        self.sample_weight.setDecimals(4)  # 4位小数
        basic_layout.addRow("样品初重(g):", self.sample_weight)

        # 操作人员
        self.operator = QLineEdit()
        basic_layout.addRow("操作人员:", self.operator)

        # 实验时间
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)  # 允许弹出日历
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())  # 设置为当前系统时间
        basic_layout.addRow("实验时间:", self.datetime_edit)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 备注说明组
        notes_group = QGroupBox("备注说明")
        notes_layout = QVBoxLayout()

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("请输入实验相关说明...")
        notes_layout.addWidget(self.notes)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # 添加弹性空间，使按钮靠右对齐

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.reset_settings)
        save_btn = QPushButton("确定")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(reset_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_experiment_types(self):
        """从实验类型管理器加载实验类型选项"""
        try:
            # 清空现有选项
            self.exp_type.clear()
            
            # 使用实验类型管理器获取所有启用的类型
            enabled_types = self.experiment_type_manager.get_enabled_types()
            
            # 添加标准类型
            for type_id, type_info in enabled_types.items():
                if type_info.category.value == "standard":
                    self.exp_type.addItem(type_info.name, type_id)
            
            # 添加自定义类型
            for type_id, type_info in enabled_types.items():
                if type_info.category.value == "custom":
                    self.exp_type.addItem(type_info.name, type_id)
                    
        except Exception as e:
            # 如果加载失败，使用默认选项
            QMessageBox.warning(self, "警告", f"加载实验类型失败：{str(e)}")
            default_types = [
                "GB/T 13240-2018 铁矿石自由膨胀指数的测定",
                "GB/T 13241-2017 铁矿石还原性能的测定", 
                "GB/T 13242-2017 铁矿石低温粉化指数的测定"
            ]
            # 与 default_types 一一对应的标准类型ID（注意 13240 为 2018 版）
            default_type_ids = ["GB_13240_2018", "GB_13241_2017", "GB_13242_2017"]
            for type_name, type_id in zip(default_types, default_type_ids):
                self.exp_type.addItem(type_name, type_id)

    def reset_settings(self):
        """重置设置"""
        try:
            # 清空所有字段
            self.project_name.clear()
            self.sample_name.clear()
            self.sample_id.clear()
            self.sample_weight.setValue(0)
            self.operator.clear()
            self.notes.clear()

            # 重置时间为当前系统时间
            self.datetime_edit.setDateTime(QDateTime.currentDateTime())

            # 重置实验类型为第一项
            self.exp_type.setCurrentIndex(0)

            # 自动生成新编号
            self.generate_sample_id()

            QMessageBox.information(self, "提示", "重置成功！")

        except Exception as e:
            QMessageBox.warning(self, "警告", f"重置失败：{str(e)}")

    def generate_sample_id(self):
        """生成样品编号"""
        try:
            # 获取实验类型ID
            mode_id = self.exp_type.currentData()
            if not mode_id:
                # 如果没有ID，使用文本匹配
                exp_type = self.exp_type.currentText()
                if "还原性能" in exp_type or "还原性" in exp_type:
                    prefix = "RED"
                elif "膨胀指数" in exp_type or "自由膨胀" in exp_type:
                    prefix = "SWE"
                elif "粉化指数" in exp_type or "低温粉化" in exp_type:
                    prefix = "RDI"
                else:
                    prefix = "TST"
            else:
                # 根据模式ID确定前缀
                if mode_id == "GB_13241_2017":
                    prefix = "RED"
                elif mode_id == "GB_13240_2018":
                    prefix = "SWE"
                elif mode_id == "GB_13242_2017":
                    prefix = "RDI"
                else:
                    # 自定义模式，使用CUS前缀
                    prefix = "CUS"

            # 获取当前系统日期
            current_date = QDateTime.currentDateTime()
            date_str = current_date.toString("yyyyMMdd")

            # 读取配置文件获取最新序号
            try:
                if os.path.exists(self.exp_config):
                    with open(self.exp_config, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        last_id = settings.get("sample_id", "")
                        if last_id and last_id.startswith(prefix) and last_id.count("-") == 2:
                            last_date = last_id.split("-")[1]
                            last_seq = int(last_id.split("-")[2])
                            if last_date == date_str:
                                seq = last_seq + 1
                            else:
                                seq = 1
                        else:
                            seq = 1
                else:
                    seq = 1
            except (json.JSONDecodeError, ValueError, KeyError, OSError):
                seq = 1

            # 生成新编号
            new_id = f"{prefix}-{date_str}-{seq:03d}"
            self.sample_id.setText(new_id)

        except Exception as e:
            QMessageBox.warning(self, "警告", f"生成编号失败：{str(e)}")
            self.sample_id.clear()

    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.exp_config):
                with open(self.exp_config, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                self.project_name.setText(settings.get("project_name", ""))
                self.sample_name.setText(settings.get("sample_name", ""))
                self.sample_id.setText(settings.get("sample_id", ""))

                exp_type = settings.get("experiment_type", "")
                if exp_type:
                    index = self.exp_type.findText(exp_type)
                    if index >= 0:
                        self.exp_type.setCurrentIndex(index)

                self.sample_weight.setValue(float(settings.get("sample_weight", 0)))
                self.operator.setText(settings.get("operator", ""))
                self.notes.setText(settings.get("notes", ""))

                # 注意：实验时间总是使用当前系统时间，不从配置文件读取
                # 确保每次打开对话框时都使用最新的当前时间
                self.datetime_edit.setDateTime(QDateTime.currentDateTime())

        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载配置文件失败：{str(e)}")

    def save_settings(self):
        """保存设置"""
        # 验证必填字段
        if not self.project_name.text().strip():
            QMessageBox.warning(self, "警告", "项目名称不能为空！")
            return

        if not self.sample_name.text().strip():
            QMessageBox.warning(self, "警告", "样品名称不能为空！")
            return

        if not self.sample_id.text().strip():
            QMessageBox.warning(self, "警告", "样品编号不能为空！")
            return

        if self.sample_weight.value() <= 0:
            QMessageBox.warning(self, "警告", "样品初重必须大于0！")
            return

        if not self.operator.text().strip():
            QMessageBox.warning(self, "警告", "操作人员不能为空！")
            return

        try:
            # 获取实验模式ID
            mode_id = self.exp_type.currentData()
            experiment_type_name = self.exp_type.currentText()
            
            settings = {
                "project_name": self.project_name.text().strip(),
                "sample_name": self.sample_name.text().strip(),
                "sample_id": self.sample_id.text().strip(),
                "experiment_type": experiment_type_name,
                "experiment_mode_id": mode_id,  # 添加模式ID
                "sample_weight": self.sample_weight.value(),
                "operator": self.operator.text().strip(),
                "date": self.datetime_edit.dateTime().toString("yyyy-MM-dd hh:mm:ss"),
                "notes": self.notes.toPlainText().strip()
            }

            # 保存到配置文件
            os.makedirs("configs", exist_ok=True)
            with open(self.exp_config, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置文件失败：{str(e)}")

    def get_experiment_params(self):
        """获取实验参数"""
        return {
            "project_name": self.project_name.text().strip(),
            "sample_name": self.sample_name.text().strip(),
            "sample_id": self.sample_id.text().strip(),
            "experiment_type": self.exp_type.currentText(),
            "experiment_mode_id": self.exp_type.currentData(),
            "sample_weight": self.sample_weight.value(),
            "operator": self.operator.text().strip(),
            "date": self.datetime_edit.dateTime().toString("yyyy-MM-dd hh:mm:ss"),
            "notes": self.notes.toPlainText().strip()
        }
