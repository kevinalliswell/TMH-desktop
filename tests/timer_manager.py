"""
时间管理器模块
用于统一管理所有定时器，减少系统资源占用，提高性能
"""

import time
from typing import Dict, Callable, Optional, Any
from PySide6.QtCore import QTimer, QObject, Signal


class TimerManager(QObject):
    """统一的时间管理器类，用于合并所有定时器功能"""
    
    # 定义信号
    timer_triggered = Signal(str)  # 定时器触发信号，传递任务名称
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建统一定时器
        self.unified_timer = QTimer(self)
        self.unified_timer.timeout.connect(self._unified_timer_callback)
        
        # 定时器任务配置
        self._tasks: Dict[str, Dict[str, Any]] = {}
        
        # 定时器状态
        self._is_running = False
        self._base_interval = 1000  # 基础间隔1秒
        
        # 计数器
        self._counters: Dict[str, int] = {}
        
        self.logger = None  # 将在外部设置
        
    def set_logger(self, logger):
        """设置日志记录器"""
        self.logger = logger
        
    def add_task(self, task_name: str, interval_seconds: int, callback: Callable, 
                 enabled: bool = True, description: str = "") -> bool:
        """
        添加定时任务
        
        Args:
            task_name: 任务名称（唯一标识）
            interval_seconds: 执行间隔（秒）
            callback: 回调函数
            enabled: 是否启用
            description: 任务描述
            
        Returns:
            bool: 添加成功返回True
        """
        try:
            if task_name in self._tasks:
                if self.logger:
                    self.logger.warning(f"任务 {task_name} 已存在，将覆盖原有配置")
            
            self._tasks[task_name] = {
                'interval_seconds': interval_seconds,
                'callback': callback,
                'enabled': enabled,
                'description': description,
                'last_execution': 0,
                'execution_count': 0
            }
            
            # 初始化计数器
            self._counters[task_name] = 0
            
            if self.logger:
                self.logger.info(f"添加定时任务: {task_name} (间隔: {interval_seconds}秒)")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"添加任务 {task_name} 失败: {str(e)}")
            return False
    
    def remove_task(self, task_name: str) -> bool:
        """
        移除定时任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            bool: 移除成功返回True
        """
        try:
            if task_name in self._tasks:
                del self._tasks[task_name]
                if task_name in self._counters:
                    del self._counters[task_name]
                
                if self.logger:
                    self.logger.info(f"移除定时任务: {task_name}")
                return True
            else:
                if self.logger:
                    self.logger.warning(f"任务 {task_name} 不存在")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"移除任务 {task_name} 失败: {str(e)}")
            return False
    
    def enable_task(self, task_name: str, enabled: bool = True) -> bool:
        """
        启用或禁用任务
        
        Args:
            task_name: 任务名称
            enabled: 是否启用
            
        Returns:
            bool: 操作成功返回True
        """
        try:
            if task_name in self._tasks:
                self._tasks[task_name]['enabled'] = enabled
                if self.logger:
                    status = "启用" if enabled else "禁用"
                    self.logger.info(f"{status}任务: {task_name}")
                return True
            else:
                if self.logger:
                    self.logger.warning(f"任务 {task_name} 不存在")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"设置任务 {task_name} 状态失败: {str(e)}")
            return False
    
    def update_task_interval(self, task_name: str, interval_seconds: int) -> bool:
        """
        更新任务执行间隔
        
        Args:
            task_name: 任务名称
            interval_seconds: 新的执行间隔（秒）
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            if task_name in self._tasks:
                self._tasks[task_name]['interval_seconds'] = interval_seconds
                if self.logger:
                    self.logger.info(f"更新任务 {task_name} 间隔: {interval_seconds}秒")
                return True
            else:
                if self.logger:
                    self.logger.warning(f"任务 {task_name} 不存在")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"更新任务 {task_name} 间隔失败: {str(e)}")
            return False
    
    def start(self) -> bool:
        """
        启动统一定时器
        
        Returns:
            bool: 启动成功返回True
        """
        try:
            if not self._is_running:
                self.unified_timer.start(self._base_interval)
                self._is_running = True
                if self.logger:
                    self.logger.info("统一定时器已启动")
                return True
            else:
                if self.logger:
                    self.logger.warning("统一定时器已在运行")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"启动统一定时器失败: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """
        停止统一定时器
        
        Returns:
            bool: 停止成功返回True
        """
        try:
            if self._is_running:
                self.unified_timer.stop()
                self._is_running = False
                if self.logger:
                    self.logger.info("统一定时器已停止")
                return True
            else:
                if self.logger:
                    self.logger.warning("统一定时器未在运行")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"停止统一定时器失败: {str(e)}")
            return False
    
    def reset_counters(self) -> None:
        """重置所有计数器"""
        for task_name in self._counters:
            self._counters[task_name] = 0
        if self.logger:
            self.logger.debug("所有定时器计数器已重置")
    
    def get_task_status(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态信息
        
        Args:
            task_name: 任务名称
            
        Returns:
            Dict: 任务状态信息，如果任务不存在返回None
        """
        if task_name in self._tasks:
            task_info = self._tasks[task_name].copy()
            task_info['counter'] = self._counters.get(task_name, 0)
            task_info['is_running'] = self._is_running
            return task_info
        return None
    
    def get_all_tasks_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务状态信息
        
        Returns:
            Dict: 所有任务状态信息
        """
        result = {}
        for task_name in self._tasks:
            result[task_name] = self.get_task_status(task_name)
        return result
    
    def is_running(self) -> bool:
        """检查定时器是否在运行"""
        return self._is_running
    
    def get_task_count(self) -> int:
        """获取任务总数"""
        return len(self._tasks)
    
    def _unified_timer_callback(self):
        """统一定时器回调函数"""
        try:
            current_time = time.time()
            
            # 更新所有计数器
            for task_name in self._counters:
                self._counters[task_name] += 1
            
            # 检查并执行到期的任务
            for task_name, task_config in self._tasks.items():
                if not task_config['enabled']:
                    continue
                
                interval_seconds = task_config['interval_seconds']
                counter = self._counters[task_name]
                
                # 检查是否到了执行时间
                if counter >= interval_seconds:
                    try:
                        # 执行回调函数
                        task_config['callback']()
                        
                        # 更新执行统计
                        task_config['last_execution'] = current_time
                        task_config['execution_count'] += 1
                        
                        # 重置计数器
                        self._counters[task_name] = 0
                        
                        # 发送信号
                        self.timer_triggered.emit(task_name)
                        
                        if self.logger:
                            self.logger.debug(f"执行任务: {task_name}")
                            
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"执行任务 {task_name} 时出错: {str(e)}")
                        
        except Exception as e:
            if self.logger:
                self.logger.error(f"统一定时器回调出错: {str(e)}")


class TimerTask:
    """定时任务配置类"""
    
    def __init__(self, name: str, interval_seconds: int, callback: Callable, 
                 description: str = "", enabled: bool = True):
        self.name = name
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.description = description
        self.enabled = enabled
        self.last_execution = 0
        self.execution_count = 0


class TimerManagerFactory:
    """定时器管理器工厂类"""
    
    @staticmethod
    def create_timer_manager(parent=None, logger=None) -> TimerManager:
        """
        创建定时器管理器实例
        
        Args:
            parent: 父对象
            logger: 日志记录器
            
        Returns:
            TimerManager: 定时器管理器实例
        """
        manager = TimerManager(parent)
        if logger:
            manager.set_logger(logger)
        return manager
    
    @staticmethod
    def create_standard_tasks(manager: TimerManager) -> None:
        """
        创建标准定时任务配置
        
        Args:
            manager: 定时器管理器实例
        """
        # 这里可以预定义一些标准任务
        # 具体任务由调用方根据需求添加
        pass


# 使用示例
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    
    app = QApplication(sys.argv)
    
    # 创建定时器管理器
    timer_manager = TimerManagerFactory.create_timer_manager()
    
    # 添加测试任务
    def test_task_1():
        print("执行任务1: 每秒执行")
    
    def test_task_2():
        print("执行任务2: 每2秒执行")
    
    def test_task_3():
        print("执行任务3: 每5秒执行")
    
    # 添加任务
    timer_manager.add_task("task_1", 1, test_task_1, True, "每秒执行的任务")
    timer_manager.add_task("task_2", 2, test_task_2, True, "每2秒执行的任务")
    timer_manager.add_task("task_3", 5, test_task_3, True, "每5秒执行的任务")
    
    # 启动定时器
    timer_manager.start()
    
    # 运行10秒后停止
    QTimer.singleShot(10000, timer_manager.stop)
    QTimer.singleShot(11000, app.quit)
    
    sys.exit(app.exec_())
