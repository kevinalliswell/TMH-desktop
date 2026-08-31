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
    exit_code = 0

    # 先装崩溃黑匣子，再构建任何窗口或设备：此前段错误和工作线程异常都不会在
    # 日志里留下痕迹（打包为 --windowed 后 stderr 无人接收）。
    from src.utils.crash_diagnostics import install as install_crash_diagnostics

    install_crash_diagnostics(logger)

    try:
        from PySide6.QtWidgets import QApplication
        from src.ui.main_window import MainWindow

        app = QApplication(sys.argv)

        # 单实例保护：串口/总线为独占资源，禁止启动第二个实例 (Issue #26)。
        # instance_lock 必须在 main() 生命周期内一直持有，退出时自动释放。
        from src.utils.single_instance import acquire_single_instance_lock
        from src.utils.audit import audit, AuditCategory, AuditResult

        instance_lock = acquire_single_instance_lock()
        if instance_lock is None:
            from PySide6.QtWidgets import QMessageBox
            logger.warning("检测到已有实例在运行，本次启动已被阻止")
            audit(AuditCategory.APP, "start_blocked",
                  result=AuditResult.REJECTED, reason="another_instance_running")
            QMessageBox.warning(
                None,
                "程序已在运行",
                "TMH-LPF-900 已经在运行中，请勿重复启动。\n\n"
                "串口与总线资源已被现有实例占用，重复启动会导致设备通信冲突。",
            )
            return

        window = MainWindow()
        window.show()

        audit(AuditCategory.APP, "start")
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

        try:
            from src.utils.audit import audit, AuditCategory
            audit(AuditCategory.APP, "exit", exit_code=exit_code)
        except Exception:
            pass
        logger.info("应用程序退出")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
