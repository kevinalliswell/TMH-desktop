"""崩溃黑匣子：让闪退在现场留下证据。

打包后的应用以 PyInstaller ``--windowed`` 方式运行，没有终端接收 stderr，
因此在此之前：

* 段错误型闪退（工作线程与串口句柄竞争导致）由内核直接终止进程，Python 层
  写不出任何东西；
* 工作线程里的未捕获异常不经过 ``sys.excepthook``，默认打到 stderr；
* GUI 线程槽函数里的未捕获异常同样只到 stderr。

三者都不会在 ``logs/app.log`` 留下一个字，所以"经常闪退但查不到原因"是必然。
本模块安装三层捕获，把证据落到磁盘：

1. ``faulthandler`` 把原生崩溃的各线程 C/Python 栈写入独立文件；
2. ``sys.excepthook`` 记录主线程未捕获异常；
3. ``threading.excepthook`` 记录工作线程未捕获异常。

安装应尽早发生（在构建任何窗口或设备之前），且必须自身绝不抛错——诊断设施
不能成为新的故障源。
"""
import faulthandler
import sys
import threading

from src.utils.logger import get_logger
from src.utils.path_manager import PathManager

_installed = False
_fault_log = None  # 保持文件对象存活；faulthandler 直接写它的文件描述符


def install(logger=None) -> bool:
    """Install the crash black box. Safe to call more than once.

    Returns:
        bool: whether the handlers are now active.
    """
    global _installed, _fault_log

    if _installed:
        return True

    logger = logger or get_logger("CrashDiagnostics")

    try:
        crash_log_path = PathManager.get_logs_path("crash.log")
    except Exception as exc:  # pragma: no cover - path layer failure
        logger.error(f"无法确定崩溃日志路径，黑匣子未安装: {exc}")
        return False

    try:
        # 追加模式：保留历次崩溃，现场排查往往需要对比。
        _fault_log = open(crash_log_path, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=_fault_log, all_threads=True)
    except Exception as exc:  # pragma: no cover - unusual IO failure
        logger.error(f"faulthandler 启用失败: {exc}")
        _fault_log = None

    def _log_main_thread_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "主线程未捕获异常", exc_info=(exc_type, exc_value, exc_tb)
        )

    def _log_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        logger.critical(
            f"工作线程未捕获异常（线程 {getattr(args.thread, 'name', '?')}）",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _log_main_thread_exception
    threading.excepthook = _log_thread_exception

    _installed = True
    logger.info(f"崩溃诊断已启用，原生崩溃栈将写入: {crash_log_path}")
    return True


def is_installed() -> bool:
    return _installed
