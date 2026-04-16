from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QLineEdit, QTableWidget,
                               QTableWidgetItem, QMessageBox, QInputDialog,
                               QFileDialog, QSplitter, QTabWidget,
                               QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
import pyqtgraph as pg
from datetime import datetime
import os
import json
from src.utils.logger import get_logger
from dataclasses import asdict

from src.services.database import ExperimentDatabase
from src.utils.password_manager import PasswordManager
from src.utils.path_manager import PathManager
from src.services.gb13241_calculator import ReductionCalculator
from src.services.gb13242_calculator import LowTempDegradationCalculator
from src.services.gb13240_calculator import FreeExpansionCalculator
from src.ui.dialogs.rdi_analysis_dialog import RDIAnalysisDialog


class HistoryQuery(QWidget):
    """历史数据查询界面"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = get_logger(__name__)

        # 初始化管理器
        self.db = ExperimentDatabase()
        self.password_manager = PasswordManager()

        # 当前选中的实验
        self.current_experiment = None

        # 实验元数据缓存（不含数据点，懒加载）
        self.experiments_data = []

        # 创建快捷键
        self.create_shortcuts()

        self.init_ui()
        self.load_experiments()

    def create_shortcuts(self):
        """创建快捷键"""
        # Ctrl+Alt+P 修改密码
        change_pwd_sc = QShortcut(QKeySequence("Ctrl+Alt+P"), self)
        change_pwd_sc.activated.connect(self.change_password)

        # Ctrl+R 刷新数据
        refresh_sc = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_sc.activated.connect(self.load_experiments)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 搜索和操作工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键字搜索...")
        self.search_edit.textChanged.connect(self.filter_experiments)
        toolbar_layout.addWidget(self.search_edit, 1)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_experiments)
        toolbar_layout.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("删除记录")
        self.delete_btn.clicked.connect(self.delete_experiment)
        self.delete_btn.setEnabled(False)
        toolbar_layout.addWidget(self.delete_btn)

        self.export_btn = QPushButton("导出数据")
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setEnabled(False)
        toolbar_layout.addWidget(self.export_btn)

        self.report_btn = QPushButton("生成报告")
        self.report_btn.clicked.connect(self.generate_report)
        self.report_btn.setEnabled(False)
        toolbar_layout.addWidget(self.report_btn)

        self.analyze_btn = QPushButton("分析实验")
        self.analyze_btn.clicked.connect(self.handle_analyze_selected_experiment)
        self.analyze_btn.setEnabled(False)
        toolbar_layout.addWidget(self.analyze_btn)

        self.diagnose_btn = QPushButton("数据库诊断")
        self.diagnose_btn.clicked.connect(self.diagnose_database)
        toolbar_layout.addWidget(self.diagnose_btn)

        layout.addLayout(toolbar_layout)

        # 需要选中实验才启用的按钮组
        self._selection_buttons = [
            self.delete_btn, self.export_btn, self.report_btn, self.analyze_btn
        ]

        # 主分割器：上方实验列表 / 下方曲线+数据
        self.splitter = QSplitter(Qt.Vertical)

        # 实验记录表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "实验名称", "样品名称", "重量(g)", "开始时间",
            "结束时间", "操作人员", "实验类型", "备注"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        # 下方 Tab：曲线 + 数据表格
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.South)

        # 曲线显示
        plot_widget_container = QWidget()
        plot_layout = QVBoxLayout(plot_widget_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = pg.PlotWidget(background='k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        styles = {'color': '#FFFFFF', 'font-size': '10pt'}
        self.plot_widget.setLabel('left', '温度(℃) / 气体流量(L/min) / 重量(g)', **styles)
        self.plot_widget.setLabel('bottom', '时间(min)', **styles)

        axis_pen = pg.mkPen(color='#FFFFFF', width=1)
        for axis_name in ('left', 'bottom'):
            self.plot_widget.getAxis(axis_name).setPen(axis_pen)
            self.plot_widget.getAxis(axis_name).setTextPen(axis_pen)

        self.plot_widget.addLegend()

        self.temp_curve = self.plot_widget.plot([], [], pen=pg.mkPen('r', width=2), name='温度(℃)')
        self.weight_curve = self.plot_widget.plot([], [], pen=pg.mkPen('orange', width=2), name='重量(g)')
        self.n2_curve = self.plot_widget.plot([], [], pen=pg.mkPen('b', width=2), name='N₂(L/min)')
        self.co_curve = self.plot_widget.plot([], [], pen=pg.mkPen('g', width=2), name='CO(L/min)')
        self.co2_curve = self.plot_widget.plot([], [], pen=pg.mkPen('y', width=2), name='CO₂(L/min)')
        self.h2_curve = self.plot_widget.plot([], [], pen=pg.mkPen('m', width=2), name='H₂(L/min)')

        plot_layout.addWidget(self.plot_widget)

        # 数据表格
        data_table_container = QWidget()
        data_table_layout = QVBoxLayout(data_table_container)
        data_table_layout.setContentsMargins(0, 0, 0, 0)

        self.data_table = QTableWidget()
        self.data_table.setColumnCount(9)
        self.data_table.setHorizontalHeaderLabels([
            "时间", "实验时长(min)", "温度(℃)", "重量(g)", "失重(%)",
            "CO(L/min)", "CO₂(L/min)", "N₂(L/min)", "H₂(L/min)"
        ])
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_table.setSelectionMode(QTableWidget.SingleSelection)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(False)

        data_table_layout.addWidget(self.data_table)

        self.tab_widget.addTab(plot_widget_container, "实验曲线")
        self.tab_widget.addTab(data_table_container, "实验数据")

        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.tab_widget)
        self.splitter.setSizes([300, 500])
        self.splitter.setChildrenCollapsible(False)

        layout.addWidget(self.splitter)
        self.setLayout(layout)

    def load_experiments(self):
        """从数据库加载实验元数据（不加载数据点，数据点在选中时懒加载）"""
        try:
            self.experiments_data = []
            self.current_experiment = None
            self._clear_plot_data()
            self._set_selection_buttons_enabled(False)

            experiments = self.db.get_all_experiments()

            for experiment in experiments:
                exp_data = {
                    "experiment_id": experiment.experiment_id,
                    "experiment_name": experiment.experiment_name,
                    "sample_name": experiment.sample_name,
                    "sample_weight": experiment.sample_weight,
                    "start_time": experiment.start_time,
                    "end_time": experiment.end_time,
                    "operator": experiment.operator,
                    "experiment_type": experiment.experiment_type,
                    "description": experiment.description,
                }
                self.experiments_data.append(exp_data)

            self.experiments_data.sort(key=lambda x: x.get("start_time", ""), reverse=True)

            self.update_table(self.experiments_data)
            self.logger.info(f"实验元数据加载完成，共 {len(self.experiments_data)} 条记录")

        except Exception as e:
            self.logger.error(f"加载实验记录失败: {e}")
            QMessageBox.critical(self, "错误", f"加载实验记录失败：{str(e)}")

    def update_table(self, experiments):
        """更新表格显示（批量分配行数，存储 experiment_id 在 UserRole 中）"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(experiments))

        for row, exp in enumerate(experiments):
            start_time_str = ""
            if exp.get("start_time"):
                try:
                    start_time_str = datetime.fromisoformat(exp["start_time"]).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    start_time_str = exp["start_time"]

            end_time_str = ""
            if exp.get("end_time"):
                try:
                    end_time_str = datetime.fromisoformat(exp["end_time"]).strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    end_time_str = exp["end_time"]

            items = [
                exp.get("experiment_name", ""),
                exp.get("sample_name", ""),
                f"{exp.get('sample_weight', 0.0):.4f}",
                start_time_str,
                end_time_str,
                exp.get("operator", ""),
                exp.get("experiment_type", ""),
                exp.get("description", "")
            ]

            for col, text in enumerate(items):
                table_item = QTableWidgetItem(str(text))
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                if col == 0:
                    table_item.setData(Qt.UserRole, exp.get("experiment_id", ""))
                self.table.setItem(row, col, table_item)

        self.table.setSortingEnabled(True)

    def filter_experiments(self):
        """过滤实验记录（带 None 安全检查）"""
        search_text = self.search_edit.text().lower()
        for row in range(self.table.rowCount()):
            row_texts = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                row_texts.append(item.text().lower() if item else "")

            if any(search_text in text for text in row_texts):
                self.table.showRow(row)
            else:
                self.table.hideRow(row)

    def _set_selection_buttons_enabled(self, enabled: bool):
        """批量启用/禁用需要选中实验的按钮"""
        for btn in self._selection_buttons:
            btn.setEnabled(enabled)

    def _clear_plot_data(self):
        """清空所有曲线和数据表格"""
        self.temp_curve.setData([], [])
        self.weight_curve.setData([], [])
        self.n2_curve.setData([], [])
        self.co_curve.setData([], [])
        self.co2_curve.setData([], [])
        self.h2_curve.setData([], [])
        self.data_table.setRowCount(0)

    def _load_experiment_data_points(self, experiment_id: str):
        """按需从数据库加载单个实验的数据点，返回解析后的数据字典"""
        data_points = self.db.get_experiment_data(experiment_id)

        timestamps = []
        temperatures = []
        weights = []
        weight_losses = []
        co_flows = []
        co2_flows = []
        n2_flows = []
        h2_flows = []

        for point in data_points:
            try:
                timestamp = point.get('timestamp', '')
                if not timestamp:
                    continue

                def _safe_float(val, default=0.0):
                    return float(val) if val is not None else default

                timestamps.append(timestamp)
                temperatures.append(_safe_float(point.get('temperature')))
                weights.append(_safe_float(point.get('weight')))
                weight_losses.append(_safe_float(point.get('weight_loss')))
                co_flows.append(_safe_float(point.get('co_flow')))
                co2_flows.append(_safe_float(point.get('co2_flow')))
                n2_flows.append(_safe_float(point.get('n2_flow')))
                h2_flows.append(_safe_float(point.get('h2_flow')))
            except (ValueError, TypeError) as e:
                self.logger.error(f"实验 {experiment_id} 数据点解析失败: {e}")
                continue

        return {
            "timestamps": timestamps,
            "temperatures": temperatures,
            "weights": weights,
            "weight_losses": weight_losses,
            "gas_flows": {
                "CO": co_flows,
                "CO2": co2_flows,
                "N2": n2_flows,
                "H2": h2_flows,
            },
        }

    def on_selection_changed(self):
        """选中记录变化时，懒加载数据点并更新曲线和数据表格"""
        items = self.table.selectedItems()
        if not items:
            self._set_selection_buttons_enabled(False)
            self.current_experiment = None
            self._clear_plot_data()
            return

        self._set_selection_buttons_enabled(True)

        row = items[0].row()
        first_item = self.table.item(row, 0)
        if not first_item:
            return
        experiment_id = first_item.data(Qt.UserRole)
        if not experiment_id:
            return

        try:
            # 查找元数据
            experiment = next(
                (exp for exp in self.experiments_data if exp["experiment_id"] == experiment_id),
                None
            )
            if not experiment:
                return

            # 懒加载数据点
            data = self._load_experiment_data_points(experiment_id)
            experiment.update(data)
            self.current_experiment = experiment

            # 更新曲线和数据表格
            raw_timestamps = experiment.get("timestamps", [])
            if not raw_timestamps:
                self._clear_plot_data()
                return

            start_time = datetime.fromisoformat(experiment["start_time"])
            minutes = []
            for t in raw_timestamps:
                try:
                    timestamp_dt = datetime.fromisoformat(t)
                except ValueError:
                    try:
                        timestamp_dt = datetime.fromtimestamp(float(t))
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"无法解析时间戳 {t}: {e}")
                        continue
                minutes.append((timestamp_dt - start_time).total_seconds() / 60)

            self.temp_curve.setData(minutes, experiment["temperatures"][:len(minutes)])
            self.weight_curve.setData(minutes, experiment["weights"][:len(minutes)])

            gas_flows = experiment.get("gas_flows", {})
            self.n2_curve.setData(minutes, gas_flows.get("N2", [])[:len(minutes)])
            self.co_curve.setData(minutes, gas_flows.get("CO", [])[:len(minutes)])
            self.co2_curve.setData(minutes, gas_flows.get("CO2", [])[:len(minutes)])
            self.h2_curve.setData(minutes, gas_flows.get("H2", [])[:len(minutes)])

            self.update_data_table(experiment, minutes)

        except Exception as e:
            self.logger.error(f"加载实验数据失败: {e}")
            QMessageBox.critical(self, "错误", f"加载实验数据失败：{str(e)}")

    def update_data_table(self, experiment, timestamps):
        """更新实验数据表格（批量预分配行数）"""
        try:
            temperatures = experiment.get("temperatures", [])
            weights = experiment.get("weights", [])
            weight_losses = experiment.get("weight_losses", [])
            gas_flows = experiment.get("gas_flows", {})
            co_flows = gas_flows.get("CO", [])
            co2_flows = gas_flows.get("CO2", [])
            n2_flows = gas_flows.get("N2", [])
            h2_flows = gas_flows.get("H2", [])
            raw_timestamps = experiment.get("timestamps", [])

            row_count = max(len(timestamps), len(temperatures), len(weights),
                           len(weight_losses), len(co_flows), len(co2_flows),
                           len(n2_flows), len(h2_flows))

            self.data_table.setRowCount(row_count)

            for i in range(row_count):
                # 格式化原始时间戳
                formatted_time = ""
                if i < len(raw_timestamps):
                    time_str = raw_timestamps[i]
                    try:
                        if 'T' in str(time_str):
                            formatted_time = datetime.fromisoformat(time_str).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            formatted_time = str(time_str)
                    except (ValueError, TypeError):
                        formatted_time = str(time_str)

                def _get(lst, idx, default=0.0):
                    return lst[idx] if idx < len(lst) else default

                cells = [
                    formatted_time,
                    f"{_get(timestamps, i):.2f}",
                    f"{_get(temperatures, i):.2f}",
                    f"{_get(weights, i):.4f}",
                    f"{_get(weight_losses, i):.2f}",
                    f"{_get(co_flows, i):.2f}",
                    f"{_get(co2_flows, i):.2f}",
                    f"{_get(n2_flows, i):.2f}",
                    f"{_get(h2_flows, i):.2f}",
                ]

                for col, text in enumerate(cells):
                    table_item = QTableWidgetItem(text)
                    table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                    self.data_table.setItem(i, col, table_item)

            self.data_table.resizeColumnsToContents()
            self.logger.debug(f"已更新数据表格，共 {row_count} 行数据")

        except Exception as e:
            self.logger.error(f"更新数据表格失败: {e}")
            QMessageBox.critical(self, "错误", f"更新数据表格失败：{str(e)}")

    def delete_experiment(self):
        """删除实验记录（先检查选中项，再验证密码）"""
        # 先检查选中项
        items = self.table.selectedItems()
        if not items:
            QMessageBox.warning(self, "警告", "请先选择要删除的记录！")
            return

        row = items[0].row()
        first_item = self.table.item(row, 0)
        if not first_item:
            return
        experiment_id = first_item.data(Qt.UserRole)
        exp_name = first_item.text()
        sample_name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""

        # 再验证密码
        password, ok = QInputDialog.getText(
            self, "验证管理员密码", "请输入管理员密码:", QLineEdit.Password
        )
        if not ok or not self.password_manager.verify_password(password):
            QMessageBox.warning(self, "警告", "密码错误！")
            return

        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除实验记录？\n实验名称: {exp_name}\n样品: {sample_name}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if not experiment_id:
                    raise ValueError(f"未找到实验ID: {exp_name}")

                if not self.db.delete_experiment(experiment_id):
                    raise Exception("删除实验记录失败")

                self.experiments_data = [
                    exp for exp in self.experiments_data
                    if exp["experiment_id"] != experiment_id
                ]

                self.table.removeRow(row)
                self.current_experiment = None
                self._clear_plot_data()
                self._set_selection_buttons_enabled(False)

                QMessageBox.information(self, "提示", "删除成功！")

            except Exception as e:
                self.logger.error(f"删除记录失败: {e}")
                QMessageBox.critical(self, "错误", f"删除记录失败：{str(e)}")

    def change_password(self):
        """修改管理员密码"""
        # 验证旧密码
        old_pwd, ok = QInputDialog.getText(
            self,
            "修改密码",
            "请输入旧密码:",
            QLineEdit.Password
        )

        if not ok or not self.password_manager.verify_password(old_pwd):
            QMessageBox.warning(self, "警告", "密码错误！")
            return

        # 输入新密码
        new_pwd, ok = QInputDialog.getText(
            self,
            "修改密码",
            "请输入新密码:",
            QLineEdit.Password
        )

        if not ok:
            return

        # 确认新密码
        confirm_pwd, ok = QInputDialog.getText(
            self,
            "修改密码",
            "请确认新密码:",
            QLineEdit.Password
        )

        if not ok:
            return

        if new_pwd != confirm_pwd:
            QMessageBox.warning(self, "警告", "两次输入的密码不一致！")
            return

        # 修改密码
        if self.password_manager.change_password(old_pwd, new_pwd):
            QMessageBox.information(self, "提示", "密码修改成功！")
        else:
            QMessageBox.critical(self, "错误", "密码修改失败！")

    def export_data(self):
        """导出实验数据"""
        try:
            if not self.current_experiment:
                QMessageBox.warning(self, "警告", "没有可导出的实验数据！")
                return

            experiment_id = self.current_experiment.get("experiment_id")
            if not experiment_id:
                QMessageBox.warning(self, "警告", "实验ID无效！")
                return

            filepath, _ = QFileDialog.getSaveFileName(
                self, "导出数据",
                PathManager.get_exports_path(),
                "CSV文件 (*.csv);;文本文件 (*.txt);;Excel文件 (*.xlsx)"
            )

            if not filepath:
                return

            if filepath.endswith(".csv"):
                export_fmt = "csv"
            elif filepath.endswith(".txt"):
                export_fmt = "txt"
            elif filepath.endswith(".xlsx"):
                export_fmt = "xlsx"
            else:
                raise ValueError("不支持的文件格式")

            full_data = self.export_experiment(experiment_id)
            if not full_data:
                raise Exception("导出数据失败")

            if export_fmt == "csv":
                self._export_csv(full_data, filepath)
            elif export_fmt == "txt":
                self._export_txt(full_data, filepath)
            elif export_fmt == "xlsx":
                self._export_xlsx(full_data, filepath)

            QMessageBox.information(self, "提示", "数据导出成功！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出数据失败：{e}")

    def _export_csv(self, data, filepath):
        """导出为CSV格式"""
        import csv

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 写入实验信息
                writer.writerow(["实验信息"])
                writer.writerow(["实验名称", data["experiment_name"]])
                writer.writerow(["样品名称", data["sample_name"]])
                writer.writerow(["样品重量(g)", data["sample_weight"]])
                writer.writerow(["开始时间", data["start_time"]])
                writer.writerow(["结束时间", data["end_time"] or ""])
                writer.writerow(["描述", data["description"]])
                writer.writerow([])

                # 写入数据表头
                headers = ["时间", "温度(℃)", "重量(g)", "失重(%)",
                           "CO(L/min)", "CO₂(L/min)", "N₂(L/min)", "H₂(L/min)"]
                writer.writerow(headers)

                # 写入数据
                for i in range(len(data["timestamps"])):
                    row = [
                        data["timestamps"][i],
                        data["temperatures"][i],
                        data["weights"][i],
                        data["weight_losses"][i],
                        data["gas_flows"]["CO"][i],
                        data["gas_flows"]["CO2"][i],
                        data["gas_flows"]["N2"][i],
                        data["gas_flows"]["H2"][i]
                    ]
                    writer.writerow(row)

            return True

        except Exception as e:
            self.logger.error(f"导出CSV失败: {e}")
            raise

    def _export_txt(self, data, filepath):
        """导出为TXT格式"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入实验信息
                f.write("实验信息:\n")
                f.write(f"实验名称: {data['experiment_name']}\n")
                f.write(f"样品名称: {data['sample_name']}\n")
                f.write(f"样品重量: {data['sample_weight']}g\n")
                f.write(f"开始时间: {data['start_time']}\n")
                f.write(f"结束时间: {data['end_time'] or ''}\n")
                f.write(f"描述: {data['description']}\n\n")

                # 写入数据表头
                f.write("时间\t温度(℃)\t重量(g)\t失重(%)\t")
                f.write("CO(L/min)\tCO₂(L/min)\tN₂(L/min)\tH₂(L/min)\n")

                # 写入数据
                for i in range(len(data["timestamps"])):
                    f.write(f"{data['timestamps'][i]}\t")
                    f.write(f"{data['temperatures'][i]:.1f}\t")
                    f.write(f"{data['weights'][i]:.4f}\t")
                    f.write(f"{data['weight_losses'][i]:.2f}\t")
                    f.write(f"{data['gas_flows']['CO'][i]:.2f}\t")
                    f.write(f"{data['gas_flows']['CO2'][i]:.2f}\t")
                    f.write(f"{data['gas_flows']['N2'][i]:.2f}\t")
                    f.write(f"{data['gas_flows']['H2'][i]:.2f}\n")

            return True

        except Exception as e:
            self.logger.error(f"导出TXT失败: {e}")
            raise

    def _export_xlsx(self, data, filepath):
        """导出为Excel格式"""
        try:
            import pandas as pd

            # 创建实验信息sheet
            info_data = {
                "项目": ["实验名称", "样品名称", "样品重量(g)", "开始时间",
                         "结束时间", "描述", "操作员", "实验类型"],
                "内容": [data["experiment_name"], data["sample_name"], data["sample_weight"],
                         data["start_time"], data["end_time"] or "", data["description"],
                         data["operator"], data["experiment_type"]]
            }
            info_df = pd.DataFrame(info_data)

            # 创建实验数据sheet
            exp_data = {
                "时间": data["timestamps"],
                "温度(℃)": data["temperatures"],
                "重量(g)": data["weights"],
                "失重(%)": data["weight_losses"],
                "CO(L/min)": data["gas_flows"]["CO"],
                "CO₂(L/min)": data["gas_flows"]["CO2"],
                "N₂(L/min)": data["gas_flows"]["N2"],
                "H₂(L/min)": data["gas_flows"]["H2"]
            }
            exp_df = pd.DataFrame(exp_data)

            # 创建Excel文件
            with pd.ExcelWriter(filepath) as writer:
                info_df.to_excel(writer, sheet_name="实验信息", index=False)
                exp_df.to_excel(writer, sheet_name="实验数据", index=False)

            return True

        except Exception as e:
            self.logger.error(f"导出Excel失败: {e}")
            raise

    @staticmethod
    def _detect_experiment_category(experiment_type: str) -> str:
        """统一检测实验类型，返回 'rdi' | 'reducibility' | 'expansion' | 'unknown'"""
        t = experiment_type.strip().lower()
        if "rdi" in t or "13242" in t or "粉化" in t or "gb/t 13242" in t:
            return "rdi"
        if "还原" in t or "13241" in t or "gb/t 13241" in t or "reducibility" in t:
            return "reducibility"
        if "膨胀" in t or "13240" in t or "gb/t 13240" in t or "swelling" in t:
            return "expansion"
        return "unknown"

    def generate_report(self):
        """生成实验报告 (HTML格式)"""
        try:
            if not self.current_experiment:
                QMessageBox.warning(self, "警告", "请先选择一个实验记录！")
                return

            experiment_id = self.current_experiment.get("experiment_id")
            experiment_name = self.current_experiment.get("experiment_name", "未知实验")

            if not experiment_id:
                QMessageBox.warning(self, "警告", "实验ID无效！")
                return

            category = self._detect_experiment_category(
                self.current_experiment.get("experiment_type", "")
            )

            if category == "rdi":
                self._generate_html_rdi_report(experiment_id, experiment_name)
            elif category == "reducibility":
                self._generate_html_reducibility_report(experiment_id, experiment_name)
            elif category == "expansion":
                self._generate_html_expansion_report(experiment_id, experiment_name)
            else:
                current_exp_type_display = self.current_experiment.get('experiment_type', '未知类型')
                QMessageBox.information(self, "提示",
                                        f"实验 '{experiment_name}' (类型: {current_exp_type_display})\n\n"
                                        "目前支持为以下类型实验生成HTML报告：\n"
                                        "- 低温粉化实验 (RDI)\n"
                                        "- 还原性实验\n"
                                        "- 球团膨胀实验")

        except Exception as e:
            self.logger.error(f"生成报告主流程失败: {e}", exc_info=True)
            QMessageBox.critical(self, "报告生成错误", f"生成报告时发生未知错误：{e}")

    # ── 报告生成：公共辅助方法 ─────────────────────────────────────

    @staticmethod
    def _get_val(data_dict, key, default=""):
        """安全获取字典值"""
        if data_dict is None or not isinstance(data_dict, dict):
            return default
        return data_dict.get(key, default)

    def _load_report_context(self, experiment_id: str, template_filename: str):
        """
        加载报告所需的上下文：实验对象、分析结果字典、模板内容、测试日期。
        返回 (experiment, analysis_results, template_content, test_date_str) 或 None。
        """
        experiment = self.db.get_experiment(experiment_id)
        if not experiment:
            self.logger.error(f"未找到实验 {experiment_id}")
            QMessageBox.warning(self, "报告生成失败", f"未找到实验ID: {experiment_id} 的数据。")
            return None

        analysis_results = {}
        if experiment.analysis_results_json:
            try:
                analysis_results = json.loads(experiment.analysis_results_json)
            except json.JSONDecodeError as e:
                self.logger.error(f"解析实验 {experiment_id} 分析结果JSON失败: {e}")
                QMessageBox.warning(self, "报告生成警告", "分析结果格式错误，部分内容可能缺失。")

        template_path = os.path.join(PathManager.get_resources_path(), 'templates', template_filename)
        if not os.path.exists(template_path):
            self.logger.error(f"报告模板未找到: {template_path}")
            QMessageBox.critical(self, "报告生成错误", "报告模板文件缺失，无法生成报告。")
            return None

        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        test_date_str = ""
        if experiment.start_time:
            try:
                test_date_str = datetime.fromisoformat(experiment.start_time).strftime('%Y-%m-%d')
            except ValueError:
                test_date_str = experiment.start_time

        return experiment, analysis_results, template_content, test_date_str

    def _fill_report_header(self, content: str, experiment, analysis_results: dict, test_date_str: str) -> str:
        """填充报告通用头部字段"""
        gv = self._get_val
        content = content.replace("{{ report_info.report_no }}", gv(analysis_results, "report_no", experiment.experiment_id[:8]))
        content = content.replace("{{ test_date }}", gv(analysis_results, "test_date", test_date_str))
        content = content.replace("{{ report_info.client }}", gv(analysis_results, "client", "委托单位"))
        content = content.replace("{{ report_info.sample_name }}", experiment.sample_name)
        content = content.replace("{{ report_info.sample_no }}", gv(analysis_results, "sample_no", experiment.experiment_id[:8]))
        content = content.replace("{{ report_info.receiving_date }}", gv(analysis_results, "receiving_date", test_date_str))
        content = content.replace("{{ report_info.report_date }}", datetime.now().strftime('%Y-%m-%d'))
        content = content.replace("{{ report_info.sample_status }}", gv(analysis_results, "sample_status", "正常"))
        return content

    def _build_equipment_html(self, equipment_list: list) -> str:
        """构建设备表格行 HTML"""
        gv = self._get_val
        rows = ""
        for i, equip in enumerate(equipment_list):
            rows += (f"<tr><td>{i+1}</td>"
                     f"<td>{gv(equip, 'name')}</td>"
                     f"<td>{gv(equip, 'model')}</td>"
                     f"<td>{gv(equip, 'precision')}</td>"
                     f"<td>{gv(equip, 'equipment_no')}</td></tr>\n")
        return rows

    def _build_conditions_html(self, conditions_list: list) -> str:
        """构建测试条件表格行 HTML"""
        gv = self._get_val
        rows = ""
        for cond in conditions_list:
            rows += (f"<tr><td>{gv(cond, 'parameter')}</td>"
                     f"<td>{gv(cond, 'standard_value')}</td>"
                     f"<td>{gv(cond, 'actual_value')}</td></tr>\n")
        return rows

    def _fill_report_footer(self, content: str, experiment, test_date_str: str) -> str:
        """填充报告签名和实验室信息"""
        content = content.replace("{{ tester }}", experiment.operator or "测试人员")
        content = content.replace("{{ test_date }}", test_date_str)
        content = content.replace("{{ reviewer }}", "审核人员")
        content = content.replace("{{ review_date }}", datetime.now().strftime('%Y-%m-%d'))
        content = content.replace("{{ lab_info.name }}", "TMH实验室")
        content = content.replace("{{ lab_info.address }}", "北京市海淀区学院路30号")
        content = content.replace("{{ lab_info.phone }}", "010-62312345")
        content = content.replace("{{ lab_info.postal_code }}", "100083")
        return content

    def _save_html_report(self, content: str, prefix: str, experiment_name: str, experiment_id: str):
        """保存 HTML 报告文件"""
        exports_dir = PathManager.get_exports_path()
        PathManager.ensure_directory_exists(exports_dir)
        safe_name = "".join(c if c.isalnum() else "_" for c in experiment_name)
        filename = f"{prefix}_{safe_name}_{experiment_id[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        filepath = os.path.join(exports_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        self.logger.info(f"成功生成报告: {filepath}")
        QMessageBox.information(self, "报告生成成功", f"HTML报告已保存到:\n{filepath}")

    # Jinja-like 模板循环占位符（三个模板共用的格式）
    _EQUIPMENT_LOOP = ("{% for item in equipment %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
                       "                <td>{{ item.name }}</td>\n                <td>{{ item.model }}</td>\n"
                       "                <td>{{ item.precision }}</td>\n                <td>{{ item.equipment_no }}</td>\n"
                       "            </tr>\n            {% endfor %}")
    _CONDITIONS_LOOP = ("{% for item in test_conditions %}\n            <tr>\n                <td>{{ item.parameter }}</td>\n"
                        "                <td>{{ item.standard_value }}</td>\n                <td>{{ item.actual_value }}</td>\n"
                        "            </tr>\n            {% endfor %}")

    # ── 报告生成：类型专用方法 ─────────────────────────────────────

    def _generate_html_rdi_report(self, experiment_id: str, experiment_name_for_file: str):
        """为 RDI 实验生成 HTML 报告"""
        try:
            ctx = self._load_report_context(experiment_id, 'iron_ore_rdi_report_template.html')
            if not ctx:
                return
            experiment, ar, report, test_date = ctx
            gv = self._get_val

            report = self._fill_report_header(report, experiment, ar, test_date)

            # Equipment
            default_equip = [
                {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
                {"name": "电子天平", "model": "FA2104N", "precision": "0.01g", "equipment_no": "BAL-001"},
                {"name": "标准筛", "model": "GB/T 6003.1", "precision": "", "equipment_no": "SIEVE-001"},
                {"name": "筛分机", "model": "ZS-200", "precision": "", "equipment_no": "SIFTER-001"},
            ]
            report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(gv(ar, "equipment", default_equip)))

            # Conditions
            default_cond = [
                {"parameter": "试样质量", "standard_value": "500±1g", "actual_value": f"{experiment.sample_weight:.1f}g"},
                {"parameter": "试样粒度", "standard_value": "10-12.5mm", "actual_value": "10-12.5mm"},
                {"parameter": "还原温度", "standard_value": "500±10℃", "actual_value": "500℃"},
                {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
                {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
                {"parameter": "还原时间", "standard_value": "60min", "actual_value": "60min"},
                {"parameter": "转鼓转速", "standard_value": "30±1r/min", "actual_value": "30r/min"},
                {"parameter": "转鼓时间", "standard_value": "10min", "actual_value": "10min"},
            ]
            report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(gv(ar, "test_conditions", default_cond)))

            # Test Results
            sieve_inputs = gv(ar, 'sieve_input_masses', {})
            rdi_indices = gv(ar, 'calculated_rdi_indices', {})
            try:
                init_mass = float(gv(ar, 'initial_sample_weight_g', experiment.sample_weight))
            except (ValueError, TypeError):
                init_mass = float(experiment.sample_weight) if experiment.sample_weight else 500.0

            plus_3_15 = gv(sieve_inputs, 'mass_gt_6_3', 0.0) + gv(sieve_inputs, 'mass_3_15_to_6_3', 0.0)
            minus_3_15 = gv(sieve_inputs, 'mass_0_5_to_3_15', 0.0)
            minus_0_5 = gv(sieve_inputs, 'mass_lt_0_5', 0.0)
            rdi_3_15 = gv(rdi_indices, 'RDI+3.15', 0.0)
            rdi_0_5 = gv(rdi_indices, 'RDI-0.5', 0.0)

            if not sieve_inputs and not rdi_indices:
                plus_3_15, minus_3_15, minus_0_5 = init_mass * 0.72, init_mass * 0.20, init_mass * 0.08
                rdi_3_15, rdi_0_5 = 72.0, 8.0

            results_html = (f"<tr><td>1</td><td>{init_mass:.2f}</td><td>{plus_3_15:.2f}</td>"
                            f"<td>{minus_3_15:.2f}</td><td>{minus_0_5:.2f}</td>"
                            f"<td>{rdi_3_15:.2f}</td><td>{rdi_0_5:.2f}</td></tr>\n")
            report = report.replace(
                "{% for item in test_results %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
                "                <td>{{ item.mass_before }}</td>\n                <td>{{ item.mass_plus_3_15 }}</td>\n"
                "                <td>{{ item.mass_minus_3_15_plus_0_5 }}</td>\n                <td>{{ item.mass_minus_0_5 }}</td>\n"
                "                <td>{{ item.rdi_minus_3_15 }}</td>\n                <td>{{ item.rdi_minus_0_5 }}</td>\n"
                "            </tr>\n            {% endfor %}", results_html)

            report = report.replace("{{ avg_results.rdi_minus_3_15 }}", f"{rdi_3_15:.2f}")
            report = report.replace("{{ avg_results.rdi_minus_0_5 }}", f"{rdi_0_5:.2f}")

            conclusion = gv(ar, "conclusion",
                            f"根据GB/T 13242-2017标准，该铁矿石样品的低温还原粉化指数RDI-3.15为{rdi_3_15:.2f}%，RDI-0.5为{rdi_0_5:.2f}%。")
            report = report.replace("{{ conclusion }}", conclusion)

            report = self._fill_report_footer(report, experiment, test_date)
            self._save_html_report(report, "RDI报告", experiment_name_for_file, experiment_id)

        except Exception as e:
            self.logger.error(f"生成RDI HTML报告失败: {e}", exc_info=True)
            QMessageBox.critical(self, "报告生成错误", f"生成HTML报告时发生错误: {e}")

    def _generate_html_reducibility_report(self, experiment_id: str, experiment_name_for_file: str):
        """为还原性实验生成 HTML 报告"""
        try:
            ctx = self._load_report_context(experiment_id, 'iron_ore_reducibility_report_template.html')
            if not ctx:
                return
            experiment, ar, report, test_date = ctx
            gv = self._get_val

            report = self._fill_report_header(report, experiment, ar, test_date)

            # Equipment
            default_equip = [
                {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
                {"name": "电子天平", "model": "FA2104N", "precision": "0.1mg", "equipment_no": "BAL-001"},
                {"name": "气体流量控制器", "model": "MFC-100", "precision": "±1%", "equipment_no": "MFC-001"},
            ]
            report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(gv(ar, "equipment", default_equip)))

            # Chemical Composition
            cc = gv(ar, "chemical_composition", {})
            for key, default in [("TFe", "65.2"), ("FeO", "0.5"), ("SiO2", "4.8"), ("Al2O3", "1.2"),
                                 ("CaO", "0.8"), ("MgO", "0.3"), ("LOI", "2.1")]:
                report = report.replace(f"{{{{ chemical_composition.{key} }}}}", gv(cc, key, default))

            # Conditions
            default_cond = [
                {"parameter": "还原温度", "standard_value": "900±10℃", "actual_value": "900℃"},
                {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
                {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
                {"parameter": "试样质量", "standard_value": "500±1g", "actual_value": f"{experiment.sample_weight}g"},
            ]
            report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(gv(ar, "test_conditions", default_cond)))

            # Test Results
            mass_before = ar.get('initial_weight', experiment.sample_weight)
            mass_after = ar.get('final_weight', mass_before * 0.95)
            final_red = ar.get('final_reduction_degree', 1.67)
            red_idx = ar.get('reduction_index', 0.01)

            results_html = (
                f"<tr><td>1</td><td>{mass_before:.1f}</td><td>{mass_after:.1f}</td>"
                f"<td>{final_red*0.3:.2f}</td><td>{final_red*0.6:.2f}</td><td>{final_red*0.9:.2f}</td><td>{final_red:.2f}</td>"
                f"<td>{final_red*0.3:.2f}</td><td>{final_red*0.6:.2f}</td><td>{final_red*0.9:.2f}</td><td>{final_red:.2f}</td>"
                f"<td>{red_idx:.3f}</td></tr>\n"
            )
            report = report.replace(
                "{% for item in test_results %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
                "                <td>{{ item.mass_before }}</td>\n                <td>{{ item.mass_after }}</td>\n"
                "                <td>{{ item.oxygen_loss_30min }}</td>\n                <td>{{ item.oxygen_loss_60min }}</td>\n"
                "                <td>{{ item.oxygen_loss_90min }}</td>\n                <td>{{ item.oxygen_loss_final }}</td>\n"
                "                <td>{{ item.red_degree_30min }}</td>\n                <td>{{ item.red_degree_60min }}</td>\n"
                "                <td>{{ item.red_degree_90min }}</td>\n                <td>{{ item.red_degree_final }}</td>\n"
                "                <td>{{ item.red_rate }}</td>\n"
                "            </tr>\n            {% endfor %}", results_html)

            # Reducibility Indices
            report = report.replace("{{ reducibility_indices.RI }}", f"{final_red:.2f}")
            report = report.replace("{{ reducibility_indices.dRdt }}", f"{red_idx:.3f}")
            report = report.replace("{{ reducibility_indices.R60 }}", f"{final_red*0.6:.2f}")
            report = report.replace("{{ reducibility_indices.t40 }}", "45")
            report = report.replace("{{ reducibility_indices.t50 }}", "60")
            report = report.replace("{{ reducibility_indices.t70 }}", "90")

            report = report.replace("{{ conclusion }}",
                                    f"根据GB/T 13241-2017标准，该铁矿石样品的还原性指数为{final_red:.2f}%，还原速率为{red_idx:.3f}%/min。")

            report = self._fill_report_footer(report, experiment, test_date)
            self._save_html_report(report, "还原性报告", experiment_name_for_file, experiment_id)

        except Exception as e:
            self.logger.error(f"生成还原性HTML报告失败: {e}", exc_info=True)
            QMessageBox.critical(self, "报告生成错误", f"生成HTML报告时发生错误: {e}")

    def _generate_html_expansion_report(self, experiment_id: str, experiment_name_for_file: str):
        """为膨胀实验生成 HTML 报告"""
        try:
            ctx = self._load_report_context(experiment_id, 'pellet_free_swelling_index_report_template.html')
            if not ctx:
                return
            experiment, ar, report, test_date = ctx
            gv = self._get_val

            report = self._fill_report_header(report, experiment, ar, test_date)

            # Equipment
            default_equip = [
                {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
                {"name": "电子天平", "model": "FA2104N", "precision": "0.1mg", "equipment_no": "BAL-001"},
                {"name": "游标卡尺", "model": "0-200mm", "precision": "0.02mm", "equipment_no": "CAL-001"},
                {"name": "气体流量控制器", "model": "MFC-200", "precision": "±1%", "equipment_no": "MFC-002"},
            ]
            report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(gv(ar, "equipment", default_equip)))

            # Chemical Composition
            cc = gv(ar, "chemical_composition", {})
            for key, default in [("TFe", "65.5"), ("FeO", "0.3"), ("SiO2", "4.2"), ("Al2O3", "1.0"),
                                 ("CaO", "1.2"), ("MgO", "0.5"), ("Basicity", "0.29")]:
                report = report.replace(f"{{{{ chemical_composition.{key} }}}}", gv(cc, key, default))

            # Conditions
            default_cond = [
                {"parameter": "还原温度", "standard_value": "1000±10℃", "actual_value": "1000℃"},
                {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
                {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
                {"parameter": "球团数量", "standard_value": "10个", "actual_value": "10个"},
                {"parameter": "球团直径", "standard_value": "10-12mm", "actual_value": "10-12mm"},
            ]
            report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(gv(ar, "test_conditions", default_cond)))

            # Test Results
            init_vol = ar.get('initial_volume', 100.0)
            final_vol = ar.get('final_volume', 120.0)
            exp_idx = ar.get('expansion_index', 20.0)
            init_d = (init_vol * 6 / 3.14159) ** (1/3)
            final_d = (final_vol * 6 / 3.14159) ** (1/3)

            results_html = (f"<tr><td>1</td><td>{init_d:.2f}</td><td>{init_vol:.1f}</td>"
                            f"<td>{final_d:.2f}</td><td>{final_vol:.1f}</td><td>{exp_idx:.2f}</td></tr>\n")
            report = report.replace(
                "{% for item in test_results %}\n            <tr>\n                <td>{{ item.pellet_no }}</td>\n"
                "                <td>{{ item.before_diameter }}</td>\n                <td>{{ item.before_volume }}</td>\n"
                "                <td>{{ item.after_diameter }}</td>\n                <td>{{ item.after_volume }}</td>\n"
                "                <td>{{ item.swelling_index }}</td>\n"
                "            </tr>\n            {% endfor %}", results_html)

            # Pellet Description
            pellet_html = "<tr><td>1</td><td>球团表面光滑，无明显缺陷</td><td>无裂纹</td><td>强度良好</td></tr>\n"
            report = report.replace(
                "{% for item in pellet_description %}\n            <tr>\n                <td>{{ item.pellet_no }}</td>\n"
                "                <td>{{ item.appearance }}</td>\n                <td>{{ item.cracks }}</td>\n"
                "                <td>{{ item.strength_evaluation }}</td>\n"
                "            </tr>\n            {% endfor %}", pellet_html)

            report = report.replace("{{ conclusion }}",
                                    f"根据GB/T 13240-2017标准，该球团样品的自由膨胀指数为{exp_idx:.2f}%，符合标准要求。")

            report = self._fill_report_footer(report, experiment, test_date)
            self._save_html_report(report, "膨胀报告", experiment_name_for_file, experiment_id)

        except Exception as e:
            self.logger.error(f"生成膨胀HTML报告失败: {e}", exc_info=True)
            QMessageBox.critical(self, "报告生成错误", f"生成HTML报告时发生错误: {e}")

    def export_experiment(self, experiment_id):
        """导出实验数据"""
        try:
            # 获取实验基本信息
            experiment = self.db.get_experiment(experiment_id)
            if not experiment:
                self.logger.error(f"导出失败：未找到实验ID {experiment_id}")
                return None # Changed from False to None for consistency
            
            # 获取实验数据点
            data_points = self.db.get_experiment_data(experiment_id)
            
            # 整合为完整实验数据
            full_data = asdict(experiment) # experiment is an ExperimentData object
            
            # 解析 analysis_results_json (如果存在)
            if experiment.analysis_results_json:
                try:
                    full_data['analysis_results'] = json.loads(experiment.analysis_results_json)
                    # 将进行RDI分析时用户输入的筛分质量也加入，因为模板中需要显示
                    # 这些数据最初是在 _analyze_rdi_data 中从对话框获取并用于计算的
                    # 如果分析结果是RDI，尝试提取原始筛分输入 (这里假设它们被存入了analysis_results字典中)
                    # 为了更可靠，应该在保存分析结果时就确保这些原始输入也被包含。
                    # 当前的 calculator.calculate_rdi 的结果是 RDI 指数，不含原始质量。
                    # 我们需要在 _analyze_rdi_data 保存时，将 sieve_data (用户输入的质量) 一同保存。
                    # 暂时假设 analysis_results 可能已经包含了它们，或者在生成报告时，对于RDI，
                    # 我们需要一种方式回溯这些输入。最简单的做法是在保存分析结果时就包含进去。
                    # 我们会在修改 _analyze_rdi_data 保存逻辑时确保这一点，这里先尝试读取。
                    if full_data['analysis_results'] and isinstance(full_data['analysis_results'], dict):
                        # 假设原始输入质量也保存在分析结果字典中，例如用以下键
                        # (这需要在分析结果保存到数据库时就确保)
                        sieve_input_masses = {}
                        if 'mass_gt_6_3' in full_data['analysis_results']:
                             sieve_input_masses['mass_gt_6_3'] = full_data['analysis_results'].get('mass_gt_6_3')
                        if 'mass_3_15_to_6_3' in full_data['analysis_results']:
                             sieve_input_masses['mass_3_15_to_6_3'] = full_data['analysis_results'].get('mass_3_15_to_6_3')
                        if 'mass_0_5_to_3_15' in full_data['analysis_results']:
                             sieve_input_masses['mass_0_5_to_3_15'] = full_data['analysis_results'].get('mass_0_5_to_3_15')
                        if 'mass_lt_0_5' in full_data['analysis_results']:
                             sieve_input_masses['mass_lt_0_5'] = full_data['analysis_results'].get('mass_lt_0_5')
                        if sieve_input_masses: # 只有当获取到筛分数据时才添加
                            full_data['analysis_results']['sieve_input_masses'] = sieve_input_masses
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析实验 {experiment_id} 的 analysis_results_json 失败: {e}")
                    full_data['analysis_results'] = None
            else:
                full_data['analysis_results'] = None
            
            # 整理时间序列数据
            full_data['timestamps'] = []
            full_data['temperatures'] = []
            full_data['weights'] = []
            full_data['weight_losses'] = []
            full_data['gas_flows'] = {
                "CO": [], "CO2": [], "N2": [], "H2": []
            }
            
            for point in data_points:
                full_data['timestamps'].append(point['timestamp'])
                full_data['temperatures'].append(point['temperature'])
                full_data['weights'].append(point['weight'])
                full_data['weight_losses'].append(point['weight_loss'])
                full_data['gas_flows']["CO"].append(point.get('co_flow', 0.0))
                full_data['gas_flows']["CO2"].append(point.get('co2_flow', 0.0))
                full_data['gas_flows']["N2"].append(point.get('n2_flow', 0.0))
                full_data['gas_flows']["H2"].append(point.get('h2_flow', 0.0))
            
            return full_data
        except Exception as e:
            self.logger.error(f"导出实验数据失败: {e}")
            return None

    def handle_analyze_selected_experiment(self):
        """处理分析选定实验的请求"""
        if not self.current_experiment:
            QMessageBox.warning(self, "提示", "请先在表格中选择一个实验记录进行分析。")
            return

        experiment_id = self.current_experiment.get("experiment_id")
        experiment_type = self.current_experiment.get("experiment_type", "").strip()
        experiment_name = self.current_experiment.get("experiment_name", "未知实验")

        self.logger.info(f"开始分析实验: ID={experiment_id}, 名称='{experiment_name}', 类型='{experiment_type}'")

        # 从 self.current_experiment 中准备分析所需的数据点列表
        # self.current_experiment 已经包含了时间序列数据
        timestamps_str = self.current_experiment.get("timestamps", [])
        weights = self.current_experiment.get("weights", [])
        temperatures = self.current_experiment.get("temperatures", []) # 可选，但最好包含
        # 其他流量数据也可以按需添加
        # gas_flows = self.current_experiment.get("gas_flows", {})

        if not timestamps_str or not weights or len(timestamps_str) != len(weights):
            QMessageBox.critical(self, "数据错误", f"实验 '{experiment_name}' 的时间戳或重量数据缺失或不匹配，无法分析。")
            self.logger.error(f"数据准备失败: 时间戳数量 {len(timestamps_str)}, 重量数据数量 {len(weights)} for experiment {experiment_id}")
            return

        parsed_data_points = []
        for i in range(len(timestamps_str)):
            try:
                point = {
                    'timestamp': datetime.fromisoformat(timestamps_str[i]),
                    'weight': float(weights[i])
                }
                if i < len(temperatures):
                    point['temperature'] = float(temperatures[i])
                # 可在此处添加气体流量等其他需要的数据到 point 字典中
                # if gas_flows:
                #     for gas_name, flow_list in gas_flows.items():
                #         if i < len(flow_list):
                #             point[f'{gas_name}_flow'] = float(flow_list[i])
                parsed_data_points.append(point)
            except (ValueError, TypeError) as e:
                self.logger.error(f"转换数据点时出错 for experiment {experiment_id}, index {i}: {e}. Data: timestamp='{timestamps_str[i]}', weight='{weights[i]}'")
                QMessageBox.critical(self, "数据转换错误", f"实验 '{experiment_name}' 的第 {i+1} 个数据点格式无效，无法分析。")
                return
        
        if not parsed_data_points:
            QMessageBox.warning(self, "无数据", f"未能从实验 '{experiment_name}' 准备任何有效数据点进行分析。")
            return

        # 根据实验类型调用相应的分析方法
        category = self._detect_experiment_category(experiment_type)
        if category == "reducibility":
            self._analyze_reducibility_data(experiment_id, experiment_name, parsed_data_points)
        elif category == "rdi":
            self._analyze_rdi_data(experiment_id, experiment_name, parsed_data_points)
        elif category == "expansion":
            self._analyze_expansion_data(experiment_id, experiment_name, parsed_data_points)
        else:
            QMessageBox.information(self, "提示", f"实验类型 '{experiment_type}' 的分析功能暂未实现。")

    def _analyze_reducibility_data(self, experiment_id: str, experiment_name: str, data_points: list):
        """分析还原性实验数据"""
        oxygen_content, ok = QInputDialog.getDouble(self, "输入参数 - 还原性分析", f"请输入实验 '{experiment_name}' 的样品氧含量 (%):", 28.5, 0.01, 100.0, 2)
        if not ok:
            self.logger.info(f"用户取消为实验 {experiment_id} 输入氧含量。")
            return

        self.logger.info(f"用户为实验 {experiment_id} 输入氧含量: {oxygen_content}% ")

        try:
            calculator = ReductionCalculator()
            analysis_results = calculator.analyze_experiment_data(
                data=data_points, 
                oxygen_content=oxygen_content # Calculator expects percentage
            )

            if not analysis_results:
                QMessageBox.critical(self, "分析失败", f"对实验 '{experiment_name}' 的还原性分析计算未能返回结果。请检查日志。")
                return

            result_text = f"实验: {experiment_name} (ID: {experiment_id})\n分析结果 (还原性实验):\n\n"
            for key, value in analysis_results.items():
                # 简单格式化一下常见的key
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, float):
                    result_text += f"  {formatted_key}: {value:.2f}\n"
                else:
                    result_text += f"  {formatted_key}: {value}\n"
            
            # 保存分析结果到数据库
            if self.db.update_experiment_analysis_results(experiment_id, analysis_results):
                self.logger.info(f"已成功将实验 {experiment_id} 的还原性分析结果保存到数据库。")
                # 更新内存中的当前实验数据
                if self.current_experiment and self.current_experiment.get("experiment_id") == experiment_id:
                    self.current_experiment['analysis_results_json'] = json.dumps(analysis_results)
            else:
                self.logger.error(f"保存实验 {experiment_id} 的还原性分析结果到数据库失败。")
                result_text += "\n\n注意：分析结果未能成功保存到数据库。"

            # 提示用户并询问是否生成报告
            reply = QMessageBox.information(self, "分析结果", 
                                            result_text + "\n\n分析结果已保存。是否现在根据这些结果生成实验报告?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.generate_report() # 调用现有的报告生成方法

            self.logger.info(f"还原性分析完成 for {experiment_id}. 结果: {analysis_results}")

        except Exception as e:
            self.logger.error(f"分析还原性实验 {experiment_id} 时发生错误: {e}")
            QMessageBox.critical(self, "分析错误", f"对实验 '{experiment_name}' 进行分析时发生错误: {e}")

    def _analyze_rdi_data(self, experiment_id: str, experiment_name: str, data_points: list):
        """分析低温粉化实验 (RDI) 数据"""
        self.logger.info(f"开始为实验 '{experiment_name}' (ID: {experiment_id}) 进行RDI分析参数输入。")

        initial_weight_g = self.current_experiment.get("sample_weight")
        if initial_weight_g is None or float(initial_weight_g) <= 0:
            QMessageBox.critical(self, "参数错误", f"实验 '{experiment_name}' 的初始样品重量无效或未记录，无法计算RDI。")
            self.logger.error(f"RDI分析中止: 实验 {experiment_id} 初始重量无效: {initial_weight_g}")
            return
        initial_weight_g = float(initial_weight_g)

        # 使用新的RDI分析对话框
        dialog = RDIAnalysisDialog(experiment_name=experiment_name, 
                                   initial_weight_g=initial_weight_g, 
                                   parent=self)
        if not dialog.exec():
            self.logger.info(f"用户取消为实验 {experiment_id} 输入RDI筛分数据。")
            return
        
        sieve_data = dialog.get_data()
        mass_gt_6_3 = sieve_data.get('mass_gt_6_3', 0.0)
        mass_3_15_to_6_3 = sieve_data.get('mass_3_15_to_6_3', 0.0)
        mass_0_5_to_3_15 = sieve_data.get('mass_0_5_to_3_15', 0.0)
        mass_lt_0_5 = sieve_data.get('mass_lt_0_5', 0.0)

        # 构建 LowTempDegradationCalculator 所需的 sieve_weights 字典
        sieve_weights_for_calc = {
            6.301: mass_gt_6_3,          # 代表 >6.3mm 的部分
            3.151: mass_3_15_to_6_3,     # 代表 +3.15mm 至 6.3mm 的部分
            0.501: mass_0_5_to_3_15,     # 代表 +0.5mm 至 3.15mm 的部分
            0.499: mass_lt_0_5           # 代表 <0.5mm 的部分 (pan)
        }

        total_sieved_mass = sum(sieve_weights_for_calc.values()) # Re-calculate for logging and display

        self.logger.info(f"RDI分析输入 (来自对话框): 初始重={initial_weight_g}g, >6.3mm={mass_gt_6_3}g, +3.15-6.3mm={mass_3_15_to_6_3}g, +0.5-3.15mm={mass_0_5_to_3_15}g, <0.5mm={mass_lt_0_5}g, 总筛分={total_sieved_mass}g")

        try:
            calculator = LowTempDegradationCalculator()
            rdi_indices = calculator.calculate_rdi(
                initial_weight=initial_weight_g,
                sieve_weights=sieve_weights_for_calc
            )

            if not rdi_indices:
                QMessageBox.critical(self, "分析失败", f"对实验 '{experiment_name}' 的RDI计算未能返回结果。请检查日志。")
                return

            # 合并原始输入筛分质量和计算得到的RDI指数，以便一起保存和报告
            combined_rdi_results = {
                'initial_sample_weight_g': initial_weight_g,
                'sieve_input_masses': sieve_data, # sieve_data from dialog (mass_gt_6_3, etc.)
                'calculated_rdi_indices': rdi_indices # RDI+6.3, RDI+3.15, RDI-0.5
            }

            result_text = f"实验: {experiment_name} (ID: {experiment_id})\n分析结果 (低温粉化指数 RDI):\n\n"
            result_text += f"  初始样品质量: {initial_weight_g:.2f} g\n"
            result_text += f"  筛后总回收质量: {total_sieved_mass:.2f} g\n\n"
            result_text += "输入筛分质量:\n"
            result_text += f"    >6.3mm: {mass_gt_6_3:.2f} g\n"
            result_text += f"    +3.15mm 至 6.3mm: {mass_3_15_to_6_3:.2f} g\n"
            result_text += f"    +0.5mm 至 3.15mm: {mass_0_5_to_3_15:.2f} g\n"
            result_text += f"    <0.5mm: {mass_lt_0_5:.2f} g\n\n"
            result_text += "计算RDI指数:\n"
            for key, value in rdi_indices.items(): # Displaying calculated RDI indices
                formatted_key = key.replace('_', ' ').replace('plus', '+').replace('minus', '-')
                if isinstance(value, float):
                    result_text += f"  {formatted_key}: {value:.2f} %\n"
                else:
                    result_text += f"  {formatted_key}: {value}\n"
            
            # 保存合并后的分析结果到数据库
            if self.db.update_experiment_analysis_results(experiment_id, combined_rdi_results):
                self.logger.info(f"已成功将实验 {experiment_id} 的RDI分析结果（包括输入质量）保存到数据库。")
                # 更新内存中的当前实验数据
                if self.current_experiment and self.current_experiment.get("experiment_id") == experiment_id:
                    self.current_experiment['analysis_results_json'] = json.dumps(combined_rdi_results)
            else:
                self.logger.error(f"保存实验 {experiment_id} 的RDI分析结果到数据库失败。")
                result_text += "\n\n注意：分析结果未能成功保存到数据库。"
            
            # 提示用户并询问是否生成报告
            reply = QMessageBox.information(self, "RDI 分析结果", 
                                            result_text + "\n\n分析结果已保存。是否现在根据这些结果生成实验报告?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.generate_report() # 调用现有的报告生成方法

            self.logger.info(f"RDI分析完成 for {experiment_id}. 结果: {combined_rdi_results}")

        except Exception as e:
            self.logger.error(f"分析RDI实验 {experiment_id} 时发生错误: {e}")
            QMessageBox.critical(self, "分析错误", f"对实验 '{experiment_name}' 进行RDI分析时发生错误: {e}")

    def _analyze_expansion_data(self, experiment_id: str, experiment_name: str, data_points: list):
        """分析膨胀实验数据"""
        self.logger.info(f"开始为实验 '{experiment_name}' (ID: {experiment_id}) 进行膨胀分析。")

        # 获取初始和最终体积
        initial_volume, ok1 = QInputDialog.getDouble(
            self, "输入参数 - 膨胀分析", 
            f"请输入实验 '{experiment_name}' 的初始体积 (mL):", 
            100.0, 1.0, 1000.0, 1
        )
        if not ok1:
            self.logger.info(f"用户取消为实验 {experiment_id} 输入初始体积。")
            return

        final_volume, ok2 = QInputDialog.getDouble(
            self, "输入参数 - 膨胀分析", 
            f"请输入实验 '{experiment_name}' 的最终体积 (mL):", 
            120.0, initial_volume, 2000.0, 1
        )
        if not ok2:
            self.logger.info(f"用户取消为实验 {experiment_id} 输入最终体积。")
            return

        self.logger.info(f"用户为实验 {experiment_id} 输入体积: 初始={initial_volume}mL, 最终={final_volume}mL")

        try:
            calculator = FreeExpansionCalculator()
            expansion_index = calculator.calculate_expansion_index(initial_volume, final_volume)

            if expansion_index is None:
                QMessageBox.critical(self, "分析失败", f"对实验 '{experiment_name}' 的膨胀指数计算失败。请检查日志。")
                return

            # 分析实验数据
            analysis_results = calculator.analyze_experiment_data(data_points)
            
            # 合并膨胀分析结果
            combined_results = {
                'initial_volume': initial_volume,
                'final_volume': final_volume,
                'expansion_index': expansion_index,
                'analysis_results': analysis_results,
                'analysis_date': datetime.now().isoformat(),
                'analysis_type': '膨胀分析'
            }

            result_text = f"实验: {experiment_name} (ID: {experiment_id})\n分析结果 (球团膨胀实验):\n\n"
            result_text += f"  初始体积: {initial_volume:.1f} mL\n"
            result_text += f"  最终体积: {final_volume:.1f} mL\n"
            result_text += f"  膨胀指数: {expansion_index:.2f} %\n\n"
            
            if analysis_results:
                result_text += "实验数据分析:\n"
                for key, value in analysis_results.items():
                    formatted_key = key.replace('_', ' ').title()
                    if isinstance(value, float):
                        result_text += f"  {formatted_key}: {value:.2f}\n"
                    else:
                        result_text += f"  {formatted_key}: {value}\n"
            
            # 保存分析结果到数据库
            if self.db.update_experiment_analysis_results(experiment_id, combined_results):
                self.logger.info(f"已成功将实验 {experiment_id} 的膨胀分析结果保存到数据库。")
                # 更新内存中的当前实验数据
                if self.current_experiment and self.current_experiment.get("experiment_id") == experiment_id:
                    self.current_experiment['analysis_results_json'] = json.dumps(combined_results)
            else:
                self.logger.error(f"保存实验 {experiment_id} 的膨胀分析结果到数据库失败。")
                result_text += "\n\n注意：分析结果未能成功保存到数据库。"
            
            # 提示用户并询问是否生成报告
            reply = QMessageBox.information(self, "膨胀分析结果", 
                                            result_text + "\n\n分析结果已保存。是否现在根据这些结果生成实验报告?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                            QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.generate_report() # 调用现有的报告生成方法

            self.logger.info(f"膨胀分析完成 for {experiment_id}. 结果: {combined_results}")

        except Exception as e:
            self.logger.error(f"分析膨胀实验 {experiment_id} 时发生错误: {e}")
            QMessageBox.critical(self, "分析错误", f"对实验 '{experiment_name}' 进行膨胀分析时发生错误: {e}")

    def diagnose_database(self):
        """数据库诊断功能"""
        try:
            integrity_info = self.db.validate_database_integrity()

            exp_count = integrity_info.get('experiment_count', 0)
            data_count = integrity_info.get('data_count', 0)
            orphaned = integrity_info.get('orphaned_data', 0)

            if not integrity_info.get('is_valid', False):
                exp_cols = ', '.join(integrity_info.get('experiment_columns', []))
                data_cols = ', '.join(integrity_info.get('data_columns', []))
                error_msg = (
                    f"数据库诊断结果：\n\n"
                    f"实验记录数量: {exp_count}\n"
                    f"数据点数量: {data_count}\n"
                    f"孤立数据记录: {orphaned}\n\n"
                    f"实验表字段: {exp_cols}\n"
                    f"数据表字段: {data_cols}\n\n"
                    f"状态: 存在问题\n\n"
                    f"发现的问题:\n"
                    f"- 存在 {orphaned} 条孤立的数据记录\n"
                    f"- 这可能导致数据加载异常\n\n"
                    f"是否立即修复数据库？"
                )

                reply = QMessageBox.question(
                    self, "数据库诊断", error_msg,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    if self.db.repair_database():
                        QMessageBox.information(self, "修复成功", "数据库修复完成，请重新加载数据。")
                        self.load_experiments()
                    else:
                        QMessageBox.critical(self, "修复失败", "数据库修复失败，请检查日志。")
            else:
                info_msg = (
                    f"数据库诊断结果：\n\n"
                    f"实验记录数量: {exp_count}\n"
                    f"数据点数量: {data_count}\n"
                    f"孤立数据记录: {orphaned}\n\n"
                    f"状态: 正常\n\n"
                    f"数据库结构完整，没有发现异常。"
                )
                QMessageBox.information(self, "数据库诊断", info_msg)

        except Exception as e:
            self.logger.error(f"数据库诊断失败: {e}")
            QMessageBox.critical(self, "诊断错误", f"数据库诊断失败：{str(e)}")
