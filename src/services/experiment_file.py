# src/services/experiment_file.py
from datetime import datetime
from typing import Optional
from dataclasses import asdict
from .database import ExperimentData
from ..utils.path_manager import PathManager
from ..utils.logger import get_logger
import json

logger = get_logger(__name__)


class ExperimentFile:
    """实验文件管理"""

    def __init__(self):
        self.file_extension = ".exp"

    def generate_filename(self, data: ExperimentData) -> str:
        """生成实验文件名"""
        # 格式：实验名称_样品名称_日期时间.exp
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{data.experiment_name}_{data.sample_name}_{date_str}"
        # 替换非法字符
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in base_name)
        return safe_name + self.file_extension

    def save_experiment(self, filepath: str, data: ExperimentData) -> bool:
        """保存实验文件"""
        try:
            # 确保目录存在
            PathManager.ensure_file_directory_exists(filepath)

            # 转换数据为字典
            exp_dict = asdict(data)

            # 添加文件格式版本信息
            file_data = {
                "version": "1.0",
                "format": "TMH_Experiment",
                "created_at": datetime.now().isoformat(),
                "data": exp_dict
            }

            # 保存为JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=4, ensure_ascii=False)

            return True

        except Exception as e:
            logger.error(f"保存实验文件失败: {e}")
            return False

    def load_experiment(self, filepath: str) -> Optional[ExperimentData]:
        """加载实验文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            # 检查文件格式
            if (file_data.get("format") != "TMH_Experiment" or
                    not file_data.get("version", "").startswith("1.")):
                raise ValueError("不支持的文件格式")

            # 转换为ExperimentData对象
            exp_dict = file_data["data"]
            return ExperimentData(**exp_dict)

        except Exception as e:
            logger.error(f"加载实验文件失败: {e}")
            return None
