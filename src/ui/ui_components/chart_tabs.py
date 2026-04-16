# src/ui/ui_components/chart_tabs.py
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
import pyqtgraph as pg
from src.utils.logger import get_logger


class ChartTabs(QTabWidget):
    """
    图表与数据表格
    包含 温度曲线 / 流量曲线 / 重量曲线 / 数据表格
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = get_logger(__name__)

        # 温度图表 - 显示所有温度传感器
        self.temp_plot = pg.PlotWidget(title="温度曲线 (时间: min)")
        self.temp_plot.setLabel('left', '温度', units='°C')
        self.temp_plot.setLabel('bottom', '时间', units='min')
        self.temp_curves = {}
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'w', 'orange']
        for i in range(9):
            pen_color = colors[i % len(colors)]
            self.temp_curves[f'T{i+1}'] = self.temp_plot.plot(pen=pen_color, name=f'T{i+1}')
        self.temp_plot.addLegend()
        self.addTab(self.temp_plot, "温度")

        # 流量图表 - 显示所有MFC
        self.flow_plot = pg.PlotWidget(title="流量曲线 (时间: min)")
        self.flow_plot.setLabel('left', '流量', units='L/min')
        self.flow_plot.setLabel('bottom', '时间', units='min')
        self.flow_curves = {}
        gases = ['N2', 'CO', 'CO2', 'H2']
        colors = ['r', 'g', 'b', 'c']
        for i, gas in enumerate(gases):
            pen_color = colors[i % len(colors)]
            self.flow_curves[gas] = self.flow_plot.plot(pen=pen_color, name=gas)
        self.flow_plot.addLegend()
        self.addTab(self.flow_plot, "流量")

        # 重量图表
        self.weight_plot = pg.PlotWidget(title="重量曲线 (时间: min)")
        self.weight_plot.setLabel('left', '重量', units='g')
        self.weight_plot.setLabel('bottom', '时间', units='min')
        self.weight_curve = self.weight_plot.plot(pen="g")
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

        # 内部缓存
        self._time = []  # 存储timestamp
        self._time_minutes = []  # 存储分钟数
        self._temperatures = {f'T{i+1}': [] for i in range(9)}
        self._flows = {'N2': [], 'CO': [], 'CO2': [], 'H2': []}
        self._weight = []
        self._experiment_start_time = None  # 实验开始时间
        
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
        temperatures, flows, weight_value = self._extract_from_frames(frames)

        if temperatures:
            self._update_temperatures(t, temperatures)
        if flows:
            self._update_flows(t, flows)
        if weight_value is not None:
            self._update_weight(t, weight_value)

        if self._table_data_enabled:
            self._insert_data_row_from_frames(
                t,
                temperatures,
                flows,
                weight_value,
                experiment_status=experiment_status,
                system_prompt=system_prompt,
                initial_weight=initial_weight
            )

    def _extract_from_frames(self, frames: dict):
        temperatures = {}
        flows = {}
        weight_value = None

        temp_frame = frames.get("temperature")
        if temp_frame and hasattr(temp_frame, "payload"):
            payload = temp_frame.payload if isinstance(temp_frame.payload, dict) else {}
            temperatures = payload.get("temperatures", {}) or {}
            if not isinstance(temperatures, dict):
                temperatures = {}

        weight_frame = frames.get("weight")
        if weight_frame and hasattr(weight_frame, "payload"):
            payload = weight_frame.payload if isinstance(weight_frame.payload, dict) else {}
            weight_value = payload.get("weight")
            if weight_value is None or not isinstance(weight_value, (int, float)) or weight_value != weight_value:
                weight_value = None

        flow_frames = frames.get("flows") if isinstance(frames.get("flows"), dict) else {}
        for gas_type, flow_frame in flow_frames.items():
            if not flow_frame or not hasattr(flow_frame, "payload"):
                continue
            payload = flow_frame.payload if isinstance(flow_frame.payload, dict) else {}
            pv = payload.get("pv")
            if pv is None or not isinstance(pv, (int, float)) or pv != pv:
                pv = None
            flows[gas_type] = pv

        return temperatures, flows, weight_value

    def _update_temperatures(self, t: float, temperatures: dict):
        if not temperatures or not isinstance(temperatures, dict):
            return
        self._time.append(t)
        if self._experiment_start_time is None:
            self._experiment_start_time = t
        minutes = (t - self._experiment_start_time) / 60.0
        self._time_minutes.append(minutes)
        for sensor, value in temperatures.items():
            if sensor in self._temperatures:
                if value is None or not isinstance(value, (int, float)) or value != value:
                    value = 0
                self._temperatures[sensor].append(value)
                min_length = min(len(self._time_minutes), len(self._temperatures[sensor]))
                if min_length > 0:
                    time_data = self._time_minutes[-min_length:]
                    temp_data = self._temperatures[sensor][-min_length:]
                    valid_temps = []
                    valid_times = []
                    for i, temp_val in enumerate(temp_data):
                        if i < len(time_data) and temp_val is not None and isinstance(temp_val, (int, float)) and not (temp_val != temp_val):
                            valid_temps.append(float(temp_val))
                            valid_times.append(time_data[i])
                    if valid_temps:
                        self.temp_curves[sensor].setData(valid_times, valid_temps)

    def _update_flows(self, t: float, flows: dict):
        if not flows or not isinstance(flows, dict):
            return
        self._time.append(t)
        if self._experiment_start_time is not None:
            minutes = (t - self._experiment_start_time) / 60.0
            self._time_minutes.append(minutes)
        for gas, flow_val in flows.items():
            if gas in self._flows:
                if flow_val is None or not isinstance(flow_val, (int, float)) or flow_val != flow_val:
                    flow_val = 0
                self._flows[gas].append(flow_val)
                if self._experiment_start_time is not None and self._time_minutes:
                    flow_len = len(self._flows[gas])
                    time_len = len(self._time_minutes)
                    if flow_len <= time_len:
                        time_data = self._time_minutes[-flow_len:]
                    else:
                        time_data = self._time_minutes[:]
                        current_time = time_data[-1] if time_data else 0
                        for _ in range(flow_len - time_len):
                            current_time += 0.1
                            time_data.append(current_time)
                    valid_flows = []
                    valid_times = []
                    for i, v in enumerate(self._flows[gas]):
                        if i < len(time_data) and v is not None and isinstance(v, (int, float)) and not (v != v):
                            valid_flows.append(float(v))
                            valid_times.append(time_data[i])
                    if valid_flows:
                        self.flow_curves[gas].setData(valid_times, valid_flows)

    def _update_weight(self, t: float, value: float):
        if value is None or not isinstance(value, (int, float)) or value != value:
            return
        self._time.append(t)
        if self._experiment_start_time is not None:
            minutes = (t - self._experiment_start_time) / 60.0
            self._time_minutes.append(minutes)
        self._weight.append(value)
        if self._experiment_start_time is not None and self._time_minutes:
            min_length = min(len(self._time_minutes), len(self._weight))
            if min_length > 0:
                time_data = self._time_minutes[-min_length:]
                weight_data = self._weight[-min_length:]
                valid_weights = []
                valid_times = []
                for i, w in enumerate(weight_data):
                    if i < len(time_data) and w is not None and isinstance(w, (int, float)) and not (w != w):
                        valid_weights.append(float(w))
                        valid_times.append(time_data[i])
                if valid_weights:
                    self.weight_curve.setData(valid_times, valid_weights)

    def _insert_data_row_from_frames(self, t: float, temperatures: dict, flows: dict, weight: float,
                                     experiment_status: str = "", system_prompt: str = "", initial_weight: float = 0.0):
        """更新数据表格的一行数据"""
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        
        # 设置实验开始时间
        if self.experiment_start_time is None:
            self.experiment_start_time = t
        
        # 时间格式化为国标时间
        import datetime
        dt = datetime.datetime.fromtimestamp(t)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 计算实验时长
        duration_seconds = int(t - self.experiment_start_time)
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # 样品温度（T8）- 处理缺失数据
        sample_temp = temperatures.get('T8', None) if temperatures else None
        self.logger.info(f" 表格 - T8温度: {sample_temp}")
        self.logger.info(f" 表格 - temperatures: {temperatures}")
        sample_temp_str = f"{sample_temp:.1f}" if sample_temp is not None and sample_temp != 0 else "--"
        
        # 气体流量PV值 - 处理缺失数据
        n2_pv = flows.get('N2', 0) if flows.get('N2') is not None else 0
        co_pv = flows.get('CO', 0) if flows.get('CO') is not None else 0
        co2_pv = flows.get('CO2', 0) if flows.get('CO2') is not None else 0
        h2_pv = flows.get('H2', 0) if flows.get('H2') is not None else 0
        
        # 计算失重和失重率
        weight_loss_str = "--"
        weight_loss_rate_str = "--"
        if initial_weight > 0 and weight is not None:
            weight_loss = initial_weight - weight
            weight_loss_rate = (weight_loss / initial_weight) * 100
            weight_loss_str = f"{weight_loss:.3f}"
            weight_loss_rate_str = f"{weight_loss_rate:.2f}"
        
        # 创建表格项
        items = [
            QTableWidgetItem(time_str),  # 时间
            QTableWidgetItem(duration_str),  # 实验时长
            QTableWidgetItem(sample_temp_str),  # 样品温度
            QTableWidgetItem(f"{n2_pv:.2f}" if n2_pv is not None else "--"),  # N2
            QTableWidgetItem(f"{co_pv:.2f}" if co_pv is not None else "--"),  # CO
            QTableWidgetItem(f"{co2_pv:.2f}" if co2_pv is not None else "--"),  # CO2
            QTableWidgetItem(f"{h2_pv:.2f}" if h2_pv is not None else "--"),  # H2
            QTableWidgetItem(f"{weight:.3f}" if weight is not None else "--"),  # 重量
            QTableWidgetItem(weight_loss_str),  # 失重
            QTableWidgetItem(weight_loss_rate_str),  # 失重率
            QTableWidgetItem(experiment_status),  # 实验状态
            QTableWidgetItem(system_prompt)  # 系统提示
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
            print(f"数据导出失败: {str(e)}")
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
            print(f"显示导出对话框失败: {str(e)}")
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
        self._temperatures = {}
        self._flows = {}
        self._weight = []
        self._time_minutes = []
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
