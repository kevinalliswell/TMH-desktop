#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.utils.path_manager import PathManager

class LoggerManager:
    """日志管理器，提供统一的日志配置"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not LoggerManager._initialized:
            # 创建日志目录
            self.log_dir = Path(PathManager.get_logs_path())
            
            # 配置根日志记录器
            self._setup_root_logger()
            
            LoggerManager._initialized = True
    
    def _setup_root_logger(self):
        """配置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除所有现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器
        file_handler = RotatingFileHandler(
            filename=str(self.log_dir / 'app.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        获取命名日志记录器
        
        Args:
            name: 日志记录器名称
            
        Returns:
            logging.Logger: 配置好的日志记录器
        """
        # 确保LoggerManager已经初始化
        LoggerManager()
        return logging.getLogger(name)

# 创建全局日志管理器实例
logger_manager = LoggerManager()

def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    return logger_manager.get_logger(name)


