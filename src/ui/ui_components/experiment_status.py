# src/ui/ui_components/experiment_status.py
from PySide6.QtWidgets import QFrame, QGroupBox, QFormLayout, QLabel, QVBoxLayout
from src.utils.logger import get_logger


class ExperimentStatus(QFrame):
    """
    实验状态栏
    包含 实验模式 / 实验计时 / 监控状态
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.labels = {}
        self.setObjectName("experimentStatus")
        self.setFrameStyle(QFrame.NoFrame)  # 移除边框
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 移除外边距
        layout.setSpacing(5)  # 进一步减少间距

        # 创建状态信息组
        status_group = QGroupBox("状态信息")
        status_layout = QFormLayout(status_group)
        status_layout.setContentsMargins(8, 8, 8, 8)  # 减小内边距
        status_layout.setSpacing(4)  # 进一步减少间距

        # 状态项配置
        status_items = [
            ("实验模式", "mode", "statusValue"),
            ("实验计时", "time", "statusValue"),
            ("实验阶段", "stage_status", "statusValue"),
            ("系统状态", "experiment_status", "statusValue")
        ]

        # 创建状态标签
        for label_text, key, style_class in status_items:
            # 创建标签文本
            lbl_name = QLabel(label_text)
            lbl_name.setObjectName("statusLabel")
            
            # 标签值
            lbl_value = QLabel("--")
            lbl_value.setObjectName(key)  # 使用key作为objectName，用于CSS选择器
            self.labels[key] = lbl_value
            
            # 使用QFormLayout的addRow方法添加标签和值
            status_layout.addRow(lbl_name, lbl_value)

        # 设置初始值
        # 另一种方式：使用 setContentsMargins 设置左间距
        self.labels["mode"].setText("待机")
        self.labels["mode"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        self.labels["time"].setText("00:00:00")
        self.labels["time"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        self.labels["stage_status"].setText("实验未开始")
        self.labels["stage_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        self.labels["experiment_status"].setText("实验未开始")
        self.labels["experiment_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素

        layout.addWidget(status_group)
        self.setLayout(layout)

    def set_status(self, mode: str = None, time_str: str = None, stage_status: str = None, 
                   experiment_status: str = None):
        """
        更新实验状态
        :param mode: 实验模式字符串
        :param time_str: 计时字符串，例如 "00:01:23"
        :param stage_status: 监控状态字符串
        :param experiment_status: 实验状态字符串
        """
        if mode is not None:
            self.labels["mode"].setText(f"{mode}")
            self.labels["mode"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        if time_str is not None:
            self.labels["time"].setText(time_str)
            self.labels["time"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        if stage_status is not None:
            self.labels["stage_status"].setText(stage_status)
            self.labels["stage_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
        if experiment_status is not None:
            self.labels["experiment_status"].setText(experiment_status)
            self.labels["experiment_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素

    def update_experiment_info(self, experiment_params):
        """更新实验信息显示"""
        try:
            experiment_type = experiment_params.get("experiment_type", "未知实验")
            sample_name = experiment_params.get("sample_name", "未知样品")
            
            # 更新实验模式显示
            self.labels["mode"].setText(f"  {experiment_type}={sample_name}")
            self.labels["stage_status"].setText("实验准备中...")
            self.labels["experiment_status"].setText("实验准备中...")
            
        except Exception as e:
            self.logger.error(f"更新实验信息失败：{e}")

    def clear_experiment_info(self):
        """清除实验信息显示"""
        try:
            self.labels["mode"].setText("待机")
            self.labels["mode"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
            self.labels["time"].setText("00:00:00")
            self.labels["time"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
            self.labels["stage_status"].setText("实验已重置，等待开始实验...")
            self.labels["stage_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
            self.labels["experiment_status"].setText("未开始")
            self.labels["experiment_status"].setContentsMargins(30, 0, 0, 0)  # 设置左侧边距为30像素
            
        except Exception as e:
            self.logger.error(f"清除实验信息失败：{e}")
    
    def update_stage_info(self, stage_info: dict):
        """
        更新详细的阶段信息显示（合并到stage_status标签）
        
        Args:
            stage_info: 包含详细阶段信息的字典
        """
        try:
            if not stage_info:
                return
            
            # 获取阶段基本信息
            stage_index = stage_info.get("current_stage_index", 0)
            total_stages = stage_info.get("total_stages", 0)
            stage_name = stage_info.get("stage_name", "未知")
            
            # 构建详细信息字符串
            current_temp = stage_info.get("current_temp", 0.0)
            target_temp = stage_info.get("target_temp", 0.0)
            elapsed_minutes = stage_info.get("elapsed_time_minutes", 0.0)
            duration_minutes = stage_info.get("duration_minutes", 0.0)
            progress = stage_info.get("progress_percent", 0.0)
            
            # 构建完整的阶段状态字符串
            if stage_index > 0 and total_stages > 0:
                stage_text = f"阶段{stage_index}/{total_stages}: {stage_name}"
            else:
                stage_text = "无实验"
            
            # 格式化详细信息
            details_parts = []
            
            # 温度信息
            if target_temp > 0:
                temp_tolerance = stage_info.get("temp_tolerance", 0.0)
                if temp_tolerance > 0:
                    details_parts.append(f"温度: {current_temp:.1f}°C (目标: {target_temp}±{temp_tolerance}°C)")
                else:
                    details_parts.append(f"温度: {current_temp:.1f}°C → {target_temp}°C")
            else:
                details_parts.append(f"温度: {current_temp:.1f}°C")
            
            # 时间信息
            if duration_minutes > 0:
                # 固定时间阶段
                details_parts.append(f"时间: {elapsed_minutes:.1f}/{duration_minutes:.0f}min")
            else:
                # 动态时间阶段（如升温、冷却）
                details_parts.append(f"时间: {elapsed_minutes:.1f}min")
            
            # 进度信息
            if progress > 0:
                details_parts.append(f"进度: {progress:.1f}%")
            
            # 合并阶段信息和详细信息
            if details_parts:
                details_text = " | ".join(details_parts)
                combined_text = f"{stage_text}\t{details_text}"
            else:
                combined_text = stage_text
            
            # 设置合并后的阶段状态信息
            self.set_status(stage_status=combined_text)
            
        except Exception as e:
            self.logger.error(f"更新阶段信息失败：{e}")
            self.set_status(stage_status="阶段信息获取失败")