#src/utils/config_loader.py

import json
import os
from functools import lru_cache
from src.utils.logger import get_logger

logger = get_logger("配置加载器")


@lru_cache(maxsize=1)
def load_comm_config(config_path: str = None) -> dict:
    """
    加载通信配置 JSON 文件（带缓存）
    优先级:
    1. 显式传入的路径
    2. 项目根目录/configs/comm_config.json
    3. 项目根目录/comm_config.json
    """
    if config_path is None:
        # 项目根目录，例如 E:\Python Projects\TMH1.0.250907
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

        # 优先尝试 configs/comm_config.json
        candidate1 = os.path.join(project_root, "configs", "comm_config.json")

        # 备用 comm_config.json
        candidate2 = os.path.join(project_root, "comm_config.json")

        if os.path.exists(candidate1):
            config_path = candidate1
        elif os.path.exists(candidate2):
            config_path = candidate2
        else:
            logger.error(f"配置文件未找到: {candidate1} 或 {candidate2}")
            return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"配置文件加载成功: {config_path}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"配置文件格式错误: {e}")
        return {}
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return {}
