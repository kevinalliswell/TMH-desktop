# src/ui/ui_components/chart_tabs.py
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
import pyqtgraph as pg
from src.ui.adapters import build_chart_table_row, map_frames_to_ui_snapshot
from src.utils.logger import get_logger


class BoundedSeries:
    """An (x, y) series capped at ``max_points`` without losing its time span.

    A live GB/T run samples at 1 Hz for hours. Appending to unbounded lists and
    re-uploading the whole history to pyqtgraph on every sample costs O(n) per
    second — around 50 ms/s after one hour and over a second after twelve, at
    which point the GUI thread can no longer keep up with its own signal queue
    and the window stops responding for the rest of the run.

    Rather than dropping the oldest points (which would erase the heating ramp
    from the chart), halve the resolution once the cap is reached and keep
    every subsequent sample at the coarser stride. Memory and per-frame cost
    stay bounded; the curve still spans the whole experiment.
    """

    def __init__(self, max_points: int):
        self._max_points = max(2, int(max_points))
        self._x = []
        self._y = []
        self._stride = 1
        self._seen = 0

    def append(self, x: float, y: float) -> None:
        self._seen += 1
        if self._seen % self._stride:
            return
        self._x.append(x)
        self._y.append(y)
        if len(self._x) > self._max_points:
            # Keep every other point; the span is preserved, the density halves.
            self._x = self._x[::2]
            self._y = self._y[::2]
            self._stride *= 2

    def clear(self) -> None:
        self._x = []
        self._y = []
        self._stride = 1
        self._seen = 0

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __len__(self) -> int:
        return len(self._x)


class ChartTabs(QTabWidget):
    """
    图表与数据表格
    包含 温度曲线 / 流量曲线 / 重量曲线 / 数据表格
    """

    # 与历史查询页保持一致的活动点上限。
    MAX_LIVE_POINTS = 5000
    # 实时表格保留的最大行数；完整记录始终在数据库里。
    MAX_TABLE_ROWS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = get_logger(__name__)

        # 温度图表 - 显示所有温度传感器
        self.temp_plot = pg.PlotWidget(title="温度曲线 (时间: min)")
        self.temp_plot.setLabel('left', '温度', units='°C')
        self.temp_plot.setLabel('bottom', '时间', units='min')
        self.temp_curves = {}
        # addLegend 必须在 plot 之前调用，否则图例捕获不到随后添加的曲线（图例为空）
        self.temp_plot.addLegend()
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'w', 'orange']
        for i in range(9):
            pen_color = colors[i % len(colors)]
            self.temp_curves[f'T{i+1}'] = self.temp_plot.plot(pen=pen_color, name=f'T{i+1}')
        self.addTab(self.temp_plot, "温度")

        # 流量图表 - 显示所有MFC
        self.flow_plot = pg.PlotWidget(title="流量曲线 (时间: min)")
        self.flow_plot.setLabel('left', '流量', units='L/min')
        self.flow_plot.setLabel('bottom', '时间', units='min')
        self.flow_curves = {}
        self.flow_plot.addLegend()
        gases = ['N2', 'CO', 'CO2', 'H2']
        colors = ['r', 'g', 'b', 'c']
        for i, gas in enumerate(gases):
            pen_color = colors[i % len(colors)]
            self.flow_curves[gas] = self.flow_plot.plot(pen=pen_color, name=gas)
        self.addTab(self.flow_plot, "流量")

        # 重量图表
        self.weight_plot = pg.PlotWidget(title="重量曲线 (时间: min)")
        self.weight_plot.setLabel('left', '重量', units='g')
        self.weight_plot.setLabel('bottom', '时间', units='min')
        self.weight_plot.addLegend()
        self.weight_curve = self.weight_plot.plot(pen="g", name="重量")
        self.addTab(self.weight_plot, "重量")

        # 数据表格 - 添加失重和失重率列
        self.data_table = QTableWidget(0, 12)
        self.data_table.setHorizontalHeaderLabels([
            "时间", "实验时长", "样品温度(℃)", "N2(L/min)", "CO(L/min)", "CO2(L/min)", "H2(L/min)", "重量(g)", "失重(g)", "失重率(%)", "实验状态", "系统提示"
        ])
        table_page = QWidget()
        table_layout = QVBoxLayout()
        table_layout.addWidget(self.data_table)
        table_page.setLayout(table_layout)
        self.addTab(table_page, "数据表")
        
        # 实验开始时间
        self.experiment_start_time = None

        # 内部缓存：每条曲线自带 x 轴，长度天然对齐，无需再做切片对齐。
        self._temperatures = {
            f'T{i+1}': BoundedSeries(self.MAX_LIVE_POINTS) for i in range(9)
        }
        self._flows = {
            gas: BoundedSeries(self.MAX_LIVE_POINTS)
            for gas in ('N2', 'CO', 'CO2', 'H2')
        }
        self._weight = BoundedSeries(self.MAX_LIVE_POINTS)
        self._experiment_start_time = None  # 实验开始时间

        # 让 pyqtgraph 只绘制可见区间并按峰值降采样（历史页已采用同样设置）。
        for curve in (
            *self.temp_curves.values(),
            *self.flow_curves.values(),
            self.weight_curve,
        ):
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
        
        # 表格数据写入控制
        self._table_data_enabled = False  # 控制是否写入表格数据
        
        # 实验信息存储
        self._experiment_info = None

    # ---- 数据更新接口 ----
    def update_from_frames(self, t: float, frames: dict, experiment_status: str = "",
                           system_prompt: str = "", initial_weight: float = 0.0):
        """统一从frames更新曲线与表格"""
        if not isinstance(frames, dict):
            return
        if not isinstance(t, (int, float)) or t != t:
            return
        snapshot = map_frames_to_ui_snapshot(frames)
        temperatures = snapshot.temperatures
        flows = snapshot.flows
        weight_value = snapshot.weight

        # Establish the shared time origin once. Each series now carries its own
        # X values, so a series that misses a frame can no longer drift against
        # the others the way the old shared-axis slicing allowed.
        if temperatures or flows or (weight_value is not None):
            if self._experiment_start_time is None:
                self._experiment_start_time = t

        if self._experiment_start_time is None:
            return
        minutes = (t - self._experiment_start_time) / 60.0

        if temperatures:
            self._update_temperatures(minutes, temperatures)
        if flows:
            self._update_flows(minutes, flows)
        if weight_value is not None:
            self._update_weight(minutes, weight_value)

        if self._table_data_enabled:
            self._insert_data_row_from_frames(
                t,
                snapshot,
                experiment_status=experiment_status,
                system_prompt=system_prompt,
                initial_weight=initial_weight
            )

    @staticmethod
    def _finite_or_zero(value) -> float:
        """Coerce a chartable value; non-numeric and NaN readings plot as 0."""
        if value is None or not isinstance(value, (int, float)) or value != value:
            return 0.0
        return float(value)

    def _update_temperatures(self, minutes: float, temperatures: dict):
        if not temperatures or not isinstance(temperatures, dict):
            return
        for sensor, value in temperatures.items():
            series = self._temperatures.get(sensor)
            if series is None:
                continue
            series.append(minutes, self._finite_or_zero(value))
            if len(series):
                self.temp_curves[sensor].setData(series.x, series.y)

    def _update_flows(self, minutes: float, flows: dict):
        if not flows or not isinstance(flows, dict):
            return
        for gas, flow_val in flows.items():
            series = self._flows.get(gas)
            if series is None:
                continue
            series.append(minutes, self._finite_or_zero(flow_val))
            if len(series):
                self.flow_curves[gas].setData(series.x, series.y)

    def _update_weight(self, minutes: float, value: float):
        if value is None or not isinstance(value, (int, float)) or value != value:
            return
        self._weight.append(minutes, float(value))
        if len(self._weight):
            self.weight_curve.setData(self._weight.x, self._weight.y)

    def _insert_data_row_from_frames(self, t: float, snapshot,
                                     experiment_status: str = "", system_prompt: str = "", initial_weight: float = 0.0):
        """更新数据表格的一行数据"""
        # 行数封顶：一场 12 小时实验会积累 4 万余行、约 50 万个 QTableWidgetItem，
        # 完整记录始终在数据库里，实时表格只需保留最近窗口。
        while self.data_table.rowCount() >= self.MAX_TABLE_ROWS:
            self.data_table.removeRow(0)

        row = self.data_table.rowCount()
        self.data_table.insertRow(row)

        # 设置实验开始时间
        if self.experiment_start_time is None:
            self.experiment_start_time = t
        row_data = build_chart_table_row(
            timestamp=t,
            snapshot=snapshot,
            experiment_start_time=self.experiment_start_time,
            experiment_status=experiment_status,
            system_prompt=system_prompt,
            initial_weight=initial_weight,
        )
        # 每秒两条 INFO 会让 GUI 线程持续排队写盘并与 6 个工作线程争同一个
        # handler 锁；采样级细节属于 DEBUG。
        self.logger.debug(" 表格 - T8温度: %s", snapshot.sample_temperature)
        self.logger.debug(" 表格 - snapshot: %s", snapshot)
        
        # 创建表格项
        items = [
            QTableWidgetItem(row_data.timestamp_text),  # 时间
            QTableWidgetItem(row_data.duration_text),  # 实验时长
            QTableWidgetItem(row_data.sample_temperature_text),  # 样品温度
            QTableWidgetItem(row_data.flow_texts["N2"]),  # N2
            QTableWidgetItem(row_data.flow_texts["CO"]),  # CO
            QTableWidgetItem(row_data.flow_texts["CO2"]),  # CO2
            QTableWidgetItem(row_data.flow_texts["H2"]),  # H2
            QTableWidgetItem(row_data.weight_text),  # 重量
            QTableWidgetItem(row_data.weight_loss_text),  # 失重
            QTableWidgetItem(row_data.weight_loss_rate_text),  # 失重率
            QTableWidgetItem(row_data.experiment_status),  # 实验状态
            QTableWidgetItem(row_data.system_prompt)  # 系统提示
        ]
        
        # 设置表格项
        for i, item in enumerate(items):
            self.data_table.setItem(row, i, item)

    # ---- 表格数据写入控制 ----
    def enable_table_data_writing(self):
        """启用表格数据写入"""
        self._table_data_enabled = True
        
    def disable_table_data_writing(self):
        """禁用表格数据写入"""
        self._table_data_enabled = False
        
    
    # ---- 数据导出功能 ----
    def export_data(self, format_type: str = 'csv', file_path: str = None, experiment_info: dict = None) -> bool:
        """
        导出表格数据
        
        Args:
            format_type: 导出格式 ('csv', 'xls', 'txt')
            file_path: 保存路径，如果为None则弹出文件选择对话框
            experiment_info: 实验信息字典
            
        Returns:
            bool: 导出是否成功
        """
        try:
            from ...utils.data_saver import DataSaver
            
            # 如果没有提供实验信息，使用存储的实验信息
            if experiment_info is None:
                experiment_info = self._experiment_info
            
            saver = DataSaver()
            return saver.save_data(
                data_table=self.data_table,
                file_path=file_path,
                format_type=format_type,
                include_headers=True,
                experiment_info=experiment_info
            )
        except Exception as e:
            self.logger.error(f"数据导出失败: {str(e)}")
            return False
    
    def show_export_dialog(self, experiment_info: dict = None) -> bool:
        """
        显示数据导出对话框
        
        Args:
            experiment_info: 实验信息字典
            
        Returns:
            bool: 是否成功导出
        """
        try:
            from ...dialogs.data_export_dialog import DataExportDialog
            
            # 如果没有提供实验信息，使用存储的实验信息
            if experiment_info is None:
                experiment_info = self._experiment_info
            
            return DataExportDialog.show_export_dialog(self.data_table, self, experiment_info)
        except Exception as e:
            self.logger.error(f"显示导出对话框失败: {str(e)}")
            return False
    
    def get_table_data_count(self) -> int:
        """
        获取表格数据行数
        
        Returns:
            int: 数据行数
        """
        return self.data_table.rowCount()
    
    def clear_table_data(self):
        """清空表格数据"""
        self.data_table.setRowCount(0)
        self.experiment_start_time = None
        # 注意：不清空 _experiment_start_time，保持监控功能
        # self._experiment_start_time = None
        self._experiment_info = None

    def clear_plot_data(self):
        """清空绘图数据（但保持监控功能）"""
        # 清空温度曲线数据
        for sensor in self.temp_curves:
            self.temp_curves[sensor].setData([], [])
        
        # 清空流量曲线数据
        for gas in self.flow_curves:
            self.flow_curves[gas].setData([], [])
        
        # 清空重量曲线数据
        self.weight_curve.setData([], [])
        
        # 清空内部数据存储，但保持实验开始时间为None
        # 这样下次数据更新时会重新设置开始时间
        # 保留传感器/气体键，否则 _update_* 的 `if sensor in self._temperatures`
        # 守卫会一直为假，清空后再也记录不到任何温度/流量点。
        for series in self._temperatures.values():
            series.clear()
        for series in self._flows.values():
            series.clear()
        self._weight.clear()
        # 注意：不清空 _experiment_start_time，让下次数据更新时重新设置
        
        # self.logger.info("已清除所有绘图数据")
    
    def set_experiment_info(self, experiment_info: dict):
        """
        设置实验信息
        
        Args:
            experiment_info: 实验信息字典
        """
        self._experiment_info = experiment_info
    
    def get_experiment_info(self) -> dict:
        """
        获取实验信息
        
        Returns:
            dict: 实验信息字典
        """
        return self._experiment_info
