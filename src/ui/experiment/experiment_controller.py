"""
向后兼容模块 - ExperimentController 已迁移至 src.controllers.experiment_controller

此文件保留为重新导出，以兼容可能存在的旧引用。
新代码应直接从 src.controllers.experiment_controller 导入。
"""
from src.controllers.experiment_controller import ExperimentController

__all__ = ["ExperimentController"]
