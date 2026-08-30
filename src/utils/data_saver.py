# src/utils/data_saver.py
"""
数据保存工具模块
支持将实验数据保存为CSV、XLS、TXT格式

注意：此模块为纯数据操作层，不依赖任何 UI 框架。
UI 相关的导出对话框已迁移至 src/ui/dialogs/data_export_dialog.py
"""

import datetime
from typing import List, Optional, Callable

from src.utils.tabular_exporter import (
    OPENPYXL_AVAILABLE,
    TabularExporter,
)


class DataSaver:
    """
    数据保存器（纯数据操作，无 UI 依赖）
    支持CSV、XLS、TXT格式的数据导出
    """

    tabular_exporter = TabularExporter
    
    def __init__(self):
        self.supported_formats = ['csv', 'xls', 'txt']
        self._progress_callback: Optional[Callable[[int], None]] = None
        self._finished_callback: Optional[Callable[[bool, str], None]] = None

    def set_progress_callback(self, callback: Callable[[int], None]):
        """设置进度回调"""
        self._progress_callback = callback

    def set_finished_callback(self, callback: Callable[[bool, str], None]):
        """设置完成回调"""
        self._finished_callback = callback

    def _emit_progress(self, progress: int):
        """发送进度通知"""
        if self._progress_callback:
            self._progress_callback(progress)

    def _emit_finished(self, success: bool, message: str):
        """发送完成通知"""
        if self._finished_callback:
            self._finished_callback(success, message)

    def save_data(self, data: List[List[str]], file_path: str,
                  format_type: str = 'csv', experiment_info: dict = None) -> bool:
        """
        保存数据到文件
        
        Args:
            data: 二维列表，已包含表头和数据行
            file_path: 保存路径
            format_type: 文件格式 ('csv', 'xls', 'txt')
            experiment_info: 实验信息字典，包含实验基本信息
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 验证格式
            if format_type.lower() not in self.supported_formats:
                raise ValueError(f"不支持的格式: {format_type}")
            
            if not data:
                raise ValueError("没有数据可保存")
            
            # 如果有实验信息，在数据前面加上实验信息
            full_data = []
            if experiment_info:
                full_data.extend(self.format_experiment_info(experiment_info))
                full_data.append([])  # 空行分隔
            full_data.extend(data)
            
            # 根据格式保存数据
            if format_type.lower() == 'csv':
                return self._save_csv(full_data, file_path)
            elif format_type.lower() == 'xls':
                return self._save_xls(full_data, file_path, experiment_info)
            elif format_type.lower() == 'txt':
                return self._save_txt(full_data, file_path)
            
            return False
                
        except Exception as e:
            self._emit_finished(False, f"保存失败: {str(e)}")
            return False

    @staticmethod
    def extract_table_data_from_widget(data_table, include_headers: bool = True) -> List[List[str]]:
        """
        从 QTableWidget 中提取数据为纯 Python 列表。
        此方法应在 UI 层调用，将 UI 数据转换为纯数据后传递给 save_data()。
        
        Args:
            data_table: QTableWidget 对象
            include_headers: 是否包含表头
            
        Returns:
            List[List[str]]: 提取的数据列表
        """
        data = []
        
        # 添加表头
        if include_headers:
            headers = []
            for col in range(data_table.columnCount()):
                header_item = data_table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"列{col+1}")
            data.append(headers)
        
        # 添加数据行
        for row in range(data_table.rowCount()):
            row_data = []
            for col in range(data_table.columnCount()):
                item = data_table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        
        return data
    
    @staticmethod
    def format_experiment_info(experiment_info: dict) -> List[List[str]]:
        """
        格式化实验信息为表格行
        
        Args:
            experiment_info: 实验信息字典
            
        Returns:
            List[List[str]]: 格式化的实验信息行
        """
        info_rows = []
        
        # 实验基本信息
        basic_info = [
            ["实验信息", ""],
            ["实验ID", experiment_info.get("experiment_id", "")],
            ["实验名称", experiment_info.get("experiment_name", "")],
            ["样品名称", experiment_info.get("sample_name", "")],
            ["样品重量", f"{experiment_info.get('sample_weight', 0):.3f} g"],
            ["实验类型", experiment_info.get("experiment_type", "")],
            ["操作员", experiment_info.get("operator", "")],
            ["开始时间", experiment_info.get("start_time", "")],
            ["结束时间", experiment_info.get("end_time", "")],
            ["描述", experiment_info.get("description", "")],
        ]
        
        info_rows.extend(basic_info)
        
        # 实验参数（如果有）
        if "experiment_params" in experiment_info:
            info_rows.append(["", ""])
            info_rows.append(["实验参数", ""])
            params = experiment_info["experiment_params"]
            for key, value in params.items():
                if key not in ["project_name", "sample_name", "sample_weight", "operator", "notes", "experiment_type"]:
                    info_rows.append([key, str(value)])
        
        # 分析结果（如果有）
        if "analysis_results" in experiment_info:
            info_rows.append(["", ""])
            info_rows.append(["分析结果", ""])
            results = experiment_info["analysis_results"]
            for key, value in results.items():
                info_rows.append([key, str(value)])
        
        return info_rows

    @staticmethod
    def generate_filename(experiment_info: dict, format_type: str) -> str:
        """
        根据实验信息生成文件名
        
        Args:
            experiment_info: 实验信息字典
            format_type: 文件格式
            
        Returns:
            str: 生成的文件名
        """
        # 获取基本信息
        experiment_name = experiment_info.get("experiment_name", "未知实验")
        sample_name = experiment_info.get("sample_name", "未知样品")
        operator = experiment_info.get("operator", "未知操作员")
        experiment_type = experiment_info.get("experiment_type", "未知类型")
        
        # 获取时间信息
        start_time = experiment_info.get("start_time", "")
        if start_time:
            try:
                if "T" in start_time:
                    dt = datetime.datetime.fromisoformat(start_time.replace("T", " "))
                else:
                    dt = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                time_str = dt.strftime("%Y%m%d_%H%M%S")
            except Exception:
                time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        else:
            time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 清理文件名中的非法字符
        def clean_filename(name):
            illegal_chars = r'<>:"/\|?*'
            for char in illegal_chars:
                name = name.replace(char, '_')
            return name[:20] if len(name) > 20 else name
        
        clean_experiment_name = clean_filename(experiment_name)
        clean_sample_name = clean_filename(sample_name)
        clean_operator = clean_filename(operator)
        clean_experiment_type = clean_filename(experiment_type)
        
        filename = f"{clean_experiment_name}_{clean_sample_name}_{clean_operator}_{clean_experiment_type}_{time_str}.{format_type.lower()}"
        
        if len(filename) > 150:
            filename = f"{clean_experiment_name}_{clean_sample_name}_{time_str}.{format_type.lower()}"
            if len(filename) > 150:
                filename = f"{clean_experiment_name}_{time_str}.{format_type.lower()}"
                if len(filename) > 150:
                    filename = f"实验数据_{time_str}.{format_type.lower()}"
        
        return filename
    
    def _save_csv(self, data: List[List[str]], file_path: str) -> bool:
        """保存为CSV格式"""
        try:
            self.tabular_exporter.write_csv(file_path, data, self._emit_progress)
            
            self._emit_finished(True, f"CSV文件保存成功: {file_path}")
            return True
            
        except Exception as e:
            self._emit_finished(False, f"CSV保存失败: {str(e)}")
            return False
    
    def _save_xls(self, data: List[List[str]], file_path: str, experiment_info: dict = None) -> bool:
        """保存为Excel格式"""
        if not OPENPYXL_AVAILABLE:
            self._emit_finished(False, "Excel保存失败: 未安装openpyxl库")
            return False
        
        try:
            # 计算表头行位置
            header_row = 1
            if experiment_info:
                header_row = len(self.format_experiment_info(experiment_info)) + 2
            self.tabular_exporter.write_xlsx(
                file_path,
                {"实验数据": data},
                header_rows={"实验数据": header_row},
                progress=self._emit_progress,
            )
            self._emit_finished(True, f"Excel文件保存成功: {file_path}")
            return True
            
        except Exception as e:
            self._emit_finished(False, f"Excel保存失败: {str(e)}")
            return False
    
    def _save_txt(self, data: List[List[str]], file_path: str) -> bool:
        """保存为TXT格式"""
        try:
            self.tabular_exporter.write_text(file_path, data, self._emit_progress)
            
            self._emit_finished(True, f"文本文件保存成功: {file_path}")
            return True
            
        except Exception as e:
            self._emit_finished(False, f"文本保存失败: {str(e)}")
            return False
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        return self.supported_formats.copy()
    
    def is_format_supported(self, format_type: str) -> bool:
        """检查格式是否支持"""
        return format_type.lower() in self.supported_formats
    
    def check_dependencies(self) -> dict:
        """检查依赖库是否可用"""
        return {
            'openpyxl': OPENPYXL_AVAILABLE,
            'csv': True,
        }
