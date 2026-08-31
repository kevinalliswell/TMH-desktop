from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QLineEdit, QTableWidget,
                               QTableWidgetItem, QMessageBox, QInputDialog,
                               QFileDialog, QSplitter, QTabWidget, QTableView,
                               QAbstractItemView, QHeaderView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
import pyqtgraph as pg
from datetime import datetime
import json
import math
from src.utils.logger import get_logger
from dataclasses import asdict

from src.application.services import (
    HistoryQueryService,
    ReportExportService,
    UnsupportedReportTypeError,
)
from src.utils.password_manager import PasswordManager
from src.services.gb13241_calculator import ReductionCalculator
from src.services.gb13242_calculator import LowTempDegradationCalculator
from src.services.gb13240_calculator import FreeExpansionCalculator
from src.ui.dialogs.rdi_analysis_dialog import RDIAnalysisDialog, suggest_drum_sample_weight
from src.ui.models.history_data_table_model import (
    HistoryDataTableModel,
    select_plot_indices,
)


class HistoryQuery(QWidget):
    """历史数据查询界面"""

    MAX_PLOT_POINTS = 5_000

    def __init__(
        self,
        parent=None,
        history_query_service=None,
        report_export_service=None,
        password_manager=None,
        is_experiment_running=None,
    ):
        super().__init__(parent)

        self.logger = get_logger(__name__)

        # 维护类操作（VACUUM/修复）会取排他锁重写整个文件，必须与运行中的
        # 1Hz 采样互斥，否则采样点会在重试耗尽后被直接丢弃。
        self._is_experiment_running = is_experiment_running

        # 初始化管理器
        self.history_query_service = history_query_service or HistoryQueryService()
        self.report_export_service = (
            report_export_service
            or ReportExportService(history_query_service=self.history_query_service)
        )
        self.password_manager = password_manager or PasswordManager()

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

        for curve in (
            self.temp_curve,
            self.weight_curve,
            self.n2_curve,
            self.co_curve,
            self.co2_curve,
            self.h2_curve,
        ):
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")

        plot_layout.addWidget(self.plot_widget)

        # 数据表格
        data_table_container = QWidget()
        data_table_layout = QVBoxLayout(data_table_container)
        data_table_layout.setContentsMargins(0, 0, 0, 0)

        self.data_table = QTableView()
        self.history_data_model = HistoryDataTableModel(self.data_table)
        self.data_table.setModel(self.history_data_model)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(False)
        self.data_table.setWordWrap(False)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate((155, 110, 90, 90, 90, 90, 90, 90, 90)):
            self.data_table.setColumnWidth(column, width)

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

            experiments = self.history_query_service.list_experiments()
            self.experiments_data = [asdict(experiment) for experiment in experiments]

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
        self.history_data_model.clear()

    def _load_experiment_data_points(self, experiment_id: str):
        """按需加载单个实验数据点，返回解析后的数据字典"""
        detail = self.history_query_service.get_experiment_detail(experiment_id)
        return asdict(detail) if detail else None

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
            if not data:
                self._clear_plot_data()
                return
            experiment.update(data)
            self.current_experiment = experiment

            # 更新曲线和数据表格
            raw_timestamps = experiment.get("timestamps", [])
            if not raw_timestamps:
                self._clear_plot_data()
                return

            start_time = datetime.fromisoformat(experiment["start_time"])
            minutes = []
            for timestamp in raw_timestamps:
                try:
                    timestamp_dt = datetime.fromisoformat(str(timestamp))
                except ValueError:
                    try:
                        timestamp_dt = datetime.fromtimestamp(float(timestamp))
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"无法解析时间戳 {timestamp}: {e}")
                        minutes.append(None)
                        continue
                minutes.append((timestamp_dt - start_time).total_seconds() / 60)

            valid_indices = [index for index, value in enumerate(minutes) if value is not None]
            gas_flows = experiment.get("gas_flows", {})
            plot_series = [
                experiment["temperatures"],
                experiment["weights"],
                gas_flows.get("N2", []),
                gas_flows.get("CO", []),
                gas_flows.get("CO2", []),
                gas_flows.get("H2", []),
            ]
            plot_indices = select_plot_indices(
                valid_indices,
                self.MAX_PLOT_POINTS,
                series=plot_series,
            )
            plot_minutes = [minutes[index] for index in plot_indices]

            def plot_values(values):
                plotted = []
                for index in plot_indices:
                    value = values[index] if index < len(values) else None
                    plotted.append(float("nan") if value is None else value)
                return plotted

            self.temp_curve.setData(plot_minutes, plot_values(experiment["temperatures"]))
            self.weight_curve.setData(plot_minutes, plot_values(experiment["weights"]))

            self.n2_curve.setData(plot_minutes, plot_values(gas_flows.get("N2", [])))
            self.co_curve.setData(plot_minutes, plot_values(gas_flows.get("CO", [])))
            self.co2_curve.setData(plot_minutes, plot_values(gas_flows.get("CO2", [])))
            self.h2_curve.setData(plot_minutes, plot_values(gas_flows.get("H2", [])))

            self.update_data_table(experiment, minutes)

        except Exception as e:
            self.logger.error(f"加载实验数据失败: {e}")
            QMessageBox.critical(self, "错误", f"加载实验数据失败：{str(e)}")

    def update_data_table(self, experiment, timestamps):
        """通过虚拟模型更新表格，不为每个数据单元创建 widget。"""
        try:
            self.history_data_model.set_experiment(experiment, timestamps)
            self.logger.debug(
                f"已更新数据表格，共 {self.history_data_model.rowCount()} 行数据"
            )

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

                if not self.history_query_service.delete_experiment(experiment_id):
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
                self.report_export_service.default_export_dir(),
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

            self.report_export_service.export_experiment_data(
                experiment_id,
                filepath,
                export_fmt,
            )

            QMessageBox.information(self, "提示", "数据导出成功！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出数据失败：{e}")

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

            output_dir = QFileDialog.getExistingDirectory(
                self,
                "选择报告保存目录",
                self.report_export_service.default_report_dir(),
                QFileDialog.ShowDirsOnly,
            )
            if not output_dir:
                return

            report_path = self.report_export_service.generate_html_report(
                experiment_id,
                output_dir=output_dir,
            )
            QMessageBox.information(self, "报告生成成功", f"HTML报告已保存到:\n{report_path}")

        except UnsupportedReportTypeError as e:
            QMessageBox.information(self, "提示", str(e))
        except Exception as e:
            self.logger.error(f"生成报告主流程失败: {e}", exc_info=True)
            QMessageBox.critical(self, "报告生成错误", f"生成报告时发生未知错误：{e}")

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
        gas_flows = self.current_experiment.get("gas_flows", {})

        if not timestamps_str or not weights or len(timestamps_str) != len(weights):
            QMessageBox.critical(self, "数据错误", f"实验 '{experiment_name}' 的时间戳或重量数据缺失或不匹配，无法分析。")
            self.logger.error(f"数据准备失败: 时间戳数量 {len(timestamps_str)}, 重量数据数量 {len(weights)} for experiment {experiment_id}")
            return

        parsed_data_points = []
        for i in range(len(timestamps_str)):
            try:
                weight = float(weights[i])
                if not math.isfinite(weight):
                    raise ValueError("weight is not finite")
                point = {
                    'timestamp': datetime.fromisoformat(timestamps_str[i]),
                    'weight': weight
                }
                # 辅助通道单独解析：温度或 CO 读数失效不得连累有效的质量数据，
                # 而且失效的 CO 必须以 None 保留下来，否则还原起点的不确定性
                # 判定看不到它，偏移结果会被当作确定值保存。
                if i < len(temperatures):
                    point['temperature'] = self._finite_or_none(temperatures[i])
                co_flows = gas_flows.get("CO", [])
                if i < len(co_flows):
                    point["co_flow"] = self._finite_or_none(co_flows[i])
                parsed_data_points.append(point)
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"跳过无效重量数据点 for experiment {experiment_id}, index {i}: "
                    f"{e}. Data: timestamp='{timestamps_str[i]}', weight='{weights[i]}'"
                )
        
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
        try:
            initial_sample_weight = float(self.current_experiment.get("sample_weight"))
        except (TypeError, ValueError):
            initial_sample_weight = 0.0
        if initial_sample_weight <= 0:
            QMessageBox.critical(self, "参数错误", "实验记录中的初始样重无效，无法计算还原度。")
            return

        total_iron_content, ok = QInputDialog.getDouble(
            self,
            "输入参数 - 还原性分析",
            f"请输入实验 '{experiment_name}' 的全铁含量 w(TFe) (%):",
            60.0,
            0.01,
            100.0,
            2,
        )
        if not ok:
            self.logger.info(f"用户取消为实验 {experiment_id} 输入全铁含量。")
            return

        feo_content, ok = QInputDialog.getDouble(
            self,
            "输入参数 - 还原性分析",
            f"请输入实验 '{experiment_name}' 的 FeO 含量 (%):",
            0.0,
            0.0,
            100.0,
            2,
        )
        if not ok:
            self.logger.info(f"用户取消为实验 {experiment_id} 输入FeO含量。")
            return

        self.logger.info(
            f"用户为实验 {experiment_id} 输入化学成分: "
            f"TFe={total_iron_content}%, FeO={feo_content}%"
        )

        try:
            calculator = ReductionCalculator()
            analysis_results = calculator.analyze_experiment_data(
                data=data_points,
                total_iron_content=total_iron_content,
                feo_content=feo_content,
                initial_sample_weight=initial_sample_weight,
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
            if self.history_query_service.update_analysis_results(experiment_id, analysis_results):
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

        try:
            initial_weight_g = float(self.current_experiment.get("sample_weight"))
        except (TypeError, ValueError):
            initial_weight_g = 0.0
        if initial_weight_g <= 0:
            QMessageBox.critical(self, "参数错误", f"实验 '{experiment_name}' 的初始样品重量无效或未记录，无法计算RDI。")
            self.logger.error(f"RDI分析中止: 实验 {experiment_id} 初始重量无效: {initial_weight_g}")
            return

        suggested_drum_mass = suggest_drum_sample_weight(data_points, initial_weight_g)

        # 使用新的RDI分析对话框
        dialog = RDIAnalysisDialog(experiment_name=experiment_name, 
                                   initial_weight_g=initial_weight_g,
                                   drum_sample_weight_g=suggested_drum_mass,
                                   parent=self)
        if not dialog.exec():
            self.logger.info(f"用户取消为实验 {experiment_id} 输入RDI筛分数据。")
            return
        
        dialog_data = dialog.get_data()
        drum_sample_weight_g = dialog_data.get('drum_sample_weight_g', 0.0)
        sieve_data = {
            key: dialog_data.get(key, 0.0)
            for key in (
                'mass_gt_6_3',
                'mass_3_15_to_6_3',
                'mass_0_5_to_3_15',
                'mass_lt_0_5',
            )
        }
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

        self.logger.info(f"RDI分析输入 (来自对话框): 初始重={initial_weight_g}g, 入鼓重={drum_sample_weight_g}g, >6.3mm={mass_gt_6_3}g, +3.15-6.3mm={mass_3_15_to_6_3}g, +0.5-3.15mm={mass_0_5_to_3_15}g, <0.5mm={mass_lt_0_5}g, 总筛分={total_sieved_mass}g")

        try:
            calculator = LowTempDegradationCalculator()
            rdi_indices = calculator.calculate_rdi(
                drum_sample_weight=drum_sample_weight_g,
                sieve_weights=sieve_weights_for_calc
            )

            if not rdi_indices:
                QMessageBox.critical(self, "分析失败", f"对实验 '{experiment_name}' 的RDI计算未能返回结果。请检查日志。")
                return

            # 合并原始输入筛分质量和计算得到的RDI指数，以便一起保存和报告
            combined_rdi_results = {
                'initial_sample_weight_g': initial_weight_g,
                'drum_sample_weight_g': drum_sample_weight_g,
                'sieve_input_masses': sieve_data, # sieve_data from dialog (mass_gt_6_3, etc.)
                'calculated_rdi_indices': rdi_indices # RDI+6.3, RDI+3.15, RDI-0.5
            }

            result_text = f"实验: {experiment_name} (ID: {experiment_id})\n分析结果 (低温粉化指数 RDI):\n\n"
            result_text += f"  初始样品质量: {initial_weight_g:.2f} g\n"
            result_text += f"  入鼓试样质量: {drum_sample_weight_g:.2f} g\n"
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
            if self.history_query_service.update_analysis_results(experiment_id, combined_rdi_results):
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
            if self.history_query_service.update_analysis_results(experiment_id, combined_results):
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

    @staticmethod
    def _finite_or_none(value):
        """Keep an auxiliary reading as a number, or as an explicit None.

        Invalid readings must survive as None rather than raising: dropping the
        row would discard the valid mass measurement alongside them, and an
        invalid CO sample has to reach the calculator for the reduction-start
        uncertainty check to see it.
        """
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _maintenance_blocked_by_running_experiment(self) -> bool:
        """Refuse VACUUM/repair while sampling is live; it would drop samples."""
        if self._is_experiment_running is None:
            return False
        try:
            return bool(self._is_experiment_running())
        except Exception as exc:  # 判定失败时保守放行，但记录原因
            self.logger.warning(f"无法确认实验运行状态，按未运行处理: {exc}")
            return False

    def diagnose_database(self):
        """数据库诊断功能"""
        if self._maintenance_blocked_by_running_experiment():
            QMessageBox.warning(
                self,
                "实验运行中",
                "实验正在运行，暂不能进行数据库诊断与修复。\n\n"
                "修复会重写整个数据库文件并长时间独占写入，期间的采样数据会丢失。\n"
                "请在实验结束后再执行。",
            )
            return
        try:
            integrity_info = asdict(self.history_query_service.validate_database_integrity())

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
                    if self.history_query_service.repair_database():
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
