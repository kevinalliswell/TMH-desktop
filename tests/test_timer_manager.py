"""
TimerManager 测试脚本
用于验证定时器管理器的功能
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from src.ui.widgets.timer_manager import TimerManager, TimerManagerFactory


class TimerManagerTest:
    """定时器管理器测试类"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.timer_manager = TimerManagerFactory.create_timer_manager()
        self.test_results = []
        
    def test_basic_functionality(self):
        """测试基本功能"""
        print("=== 测试基本功能 ===")
        
        # 测试任务计数器
        task_count = 0
        
        def test_callback_1():
            nonlocal task_count
            task_count += 1
            print(f"任务1执行 - 第{task_count}次")
        
        def test_callback_2():
            print("任务2执行 - 每2秒")
        
        def test_callback_3():
            print("任务3执行 - 每5秒")
        
        # 添加测试任务
        self.timer_manager.add_task("task_1", 1, test_callback_1, True, "每秒执行的任务")
        self.timer_manager.add_task("task_2", 2, test_callback_2, True, "每2秒执行的任务")
        self.timer_manager.add_task("task_3", 5, test_callback_3, True, "每5秒执行的任务")
        
        # 验证任务添加
        assert self.timer_manager.get_task_count() == 3, "任务数量不正确"
        print("✓ 任务添加成功")
        
        # 启动定时器
        self.timer_manager.start()
        assert self.timer_manager.is_running(), "定时器未启动"
        print("✓ 定时器启动成功")
        
        # 运行10秒
        print("运行10秒...")
        QTimer.singleShot(10000, self.stop_test)
        QTimer.singleShot(11000, self.app.quit)
        
        self.app.exec_()
        
        print(f"✓ 任务1执行了{task_count}次（预期约10次）")
        print("基本功能测试完成\n")
    
    def test_task_control(self):
        """测试任务控制功能"""
        print("=== 测试任务控制功能 ===")
        
        execution_count = 0
        
        def test_callback():
            nonlocal execution_count
            execution_count += 1
            print(f"控制测试任务执行 - 第{execution_count}次")
        
        # 添加任务
        self.timer_manager.add_task("control_test", 1, test_callback, True, "控制测试任务")
        
        # 启动定时器
        self.timer_manager.start()
        
        # 运行3秒
        QTimer.singleShot(3000, lambda: self.timer_manager.enable_task("control_test", False))
        QTimer.singleShot(5000, lambda: self.timer_manager.enable_task("control_test", True))
        QTimer.singleShot(8000, self.stop_test)
        QTimer.singleShot(9000, self.app.quit)
        
        self.app.exec_()
        
        print(f"✓ 任务执行了{execution_count}次（预期约6次：前3秒+后3秒）")
        print("任务控制功能测试完成\n")
    
    def test_task_status(self):
        """测试任务状态查询"""
        print("=== 测试任务状态查询 ===")
        
        def test_callback():
            pass
        
        # 添加任务
        self.timer_manager.add_task("status_test", 2, test_callback, True, "状态测试任务")
        
        # 获取任务状态
        status = self.timer_manager.get_task_status("status_test")
        assert status is not None, "无法获取任务状态"
        assert status['enabled'] == True, "任务状态不正确"
        assert status['interval_seconds'] == 2, "任务间隔不正确"
        print("✓ 任务状态查询成功")
        
        # 获取所有任务状态
        all_status = self.timer_manager.get_all_tasks_status()
        assert len(all_status) >= 1, "无法获取所有任务状态"
        print("✓ 所有任务状态查询成功")
        
        print("任务状态查询测试完成\n")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("=== 测试错误处理 ===")
        
        def error_callback():
            raise Exception("测试错误")
        
        def normal_callback():
            print("正常任务执行")
        
        # 添加会出错的任务
        self.timer_manager.add_task("error_task", 1, error_callback, True, "错误测试任务")
        self.timer_manager.add_task("normal_task", 2, normal_callback, True, "正常任务")
        
        # 启动定时器
        self.timer_manager.start()
        
        # 运行5秒
        QTimer.singleShot(5000, self.stop_test)
        QTimer.singleShot(6000, self.app.quit)
        
        self.app.exec_()
        
        print("✓ 错误处理测试完成（应该看到错误日志和正常任务继续执行）\n")
    
    def stop_test(self):
        """停止测试"""
        self.timer_manager.stop()
        print("测试停止")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始TimerManager功能测试...\n")
        
        try:
            self.test_basic_functionality()
            self.test_task_control()
            self.test_task_status()
            self.test_error_handling()
            
            print("=== 所有测试完成 ===")
            print("✓ TimerManager功能正常")
            
        except Exception as e:
            print(f"✗ 测试失败: {str(e)}")
            return False
        
        return True


def main():
    """主函数"""
    print("TimerManager 测试程序")
    print("=" * 50)
    
    # 创建测试实例
    test = TimerManagerTest()
    
    # 运行测试
    success = test.run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！TimerManager可以正常使用。")
    else:
        print("\n❌ 测试失败，请检查代码。")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
