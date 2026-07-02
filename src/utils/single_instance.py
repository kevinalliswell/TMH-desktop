"""单实例运行保护 (Issue #26)。

桌面程序若被重复启动，第二个实例会与第一个实例争抢同一批串口 / 总线资源，
造成设备通信冲突。本模块基于 :class:`QSharedMemory` 提供跨平台的单实例检测：
第一个实例创建一段命名共享内存并在整个进程生命周期内持有；后续实例创建失败，
即可判定已有实例在运行。

Windows（生产目标平台）在进程退出时会自动释放共享内存段；POSIX 上进程异常
崩溃可能残留段，故创建前先尝试 attach/detach 清理陈旧段。
"""

from PySide6.QtCore import QSharedMemory

# 共享内存键需在本应用内唯一且稳定
SINGLE_INSTANCE_KEY = "TMH-LPF-900-single-instance"


class SingleInstanceGuard:
    """基于共享内存的单实例守卫。

    典型用法::

        guard = SingleInstanceGuard()
        if not guard.try_acquire():
            # 已有实例在运行，提示并退出
            ...
        # 需在应用整个生命周期内持有 guard 引用，避免被 GC 释放
    """

    def __init__(self, key: str = SINGLE_INSTANCE_KEY):
        self._shared = QSharedMemory(key)
        self._acquired = False

    def try_acquire(self) -> bool:
        """尝试获取单实例锁。

        Returns:
            bool: 获取成功（当前为唯一实例）返回 True；已有实例在运行返回 False。
        """
        # 清理异常退出遗留的共享内存段（仅 POSIX 需要；Windows 会自动释放）。
        # 若确有其它实例存活，其自身仍持有该段，create() 仍会失败。
        if self._shared.attach():
            self._shared.detach()

        if self._shared.create(1):
            self._acquired = True
            return True
        return False

    def release(self) -> None:
        """释放单实例锁（进程退出前调用；正常退出时可省略）。"""
        if self._acquired and self._shared.isAttached():
            self._shared.detach()
            self._acquired = False
