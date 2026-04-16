# src/app.py

import sys
import os
import traceback

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.logger import get_logger


def main():
    """应用程序主入口，包含全局异常处理和资源清理"""
    logger = get_logger("App")
    window = None
    app = None

    try:
        from PySide6.QtWidgets import QApplication
        from src.ui.main_window import MainWindow

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()

        logger.info("应用程序启动成功")
        exit_code = app.exec()

    except Exception as e:
        logger.critical(f"应用程序发生致命错误: {e}")
        logger.critical(traceback.format_exc())
        exit_code = 1

    finally:
        # 确保资源正确释放
        try:
            if window and hasattr(window, 'runtime') and window.runtime:
                window.runtime.stop()
                logger.info("运行时服务已在退出时清理")
        except Exception as cleanup_err:
            logger.error(f"退出清理时发生错误: {cleanup_err}")

        logger.info("应用程序退出")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
