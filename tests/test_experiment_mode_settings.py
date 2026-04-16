#!/usr/bin/env python3
"""
测试实验模式设置页面
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from src.ui.pages.experiment_mode_settings_page import ExperimentModeSettingsPage

def main():
    app = QApplication(sys.argv)
    
    # 创建实验模式设置页面
    page = ExperimentModeSettingsPage()
    page.show()
    
    print("实验模式设置页面已启动")
    print("功能说明：")
    print("1. 左侧显示标准实验模式和自定义实验模式列表")
    print("2. 标准实验模式为只读，可以查看详细信息")
    print("3. 自定义实验模式可以编辑、添加、删除")
    print("4. 可以添加、编辑、删除实验阶段")
    print("5. 所有修改会自动保存到JSON配置文件")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
