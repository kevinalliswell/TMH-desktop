"""系统级审计日志 (Issue #34)。

在诊断日志 (app.log) 之外，单独记录项目过程中的关键业务操作，形成一条
结构化、按天滚动、不与普通调试日志混杂的审计轨迹，便于事后追溯：
谁 在 何时 执行了 什么 关键操作、结果如何。

设计要点：
- 独立 logger (``tmh.audit``)，``propagate=False``，不污染 app.log / 控制台；
- 每条记录为一行 JSON，字段固定（ts/category/action/result/operator/detail），
  便于机器解析与检索；
- 按天滚动 (``audit.log`` + ``audit.log.YYYY-MM-DD``)，默认保留约半年；
- 写入失败绝不抛出，避免审计影响主业务流程。
"""

import json
import logging
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from src.utils.path_manager import PathManager


class AuditCategory:
    """审计事件分类。"""

    APP = "APP"                # 应用启动/退出/被阻止
    EXPERIMENT = "EXPERIMENT"  # 实验开始/停止/完成/模式切换
    GAS = "GAS"                # 气体流量设定等 MFC 操作
    BALANCE = "BALANCE"        # 天平去皮等操作
    EXPORT = "EXPORT"          # 数据导出/报告生成
    AUTH = "AUTH"              # 登录校验/密码修改
    CONFIG = "CONFIG"          # 配置变更


class AuditResult:
    """审计事件结果。"""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REJECTED = "REJECTED"


class _AuditLogger:
    """审计日志单例，负责配置独立的滚动文件处理器。"""

    _instance: Optional["_AuditLogger"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "_AuditLogger":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._init_logger()
                cls._instance = instance
        return cls._instance

    def _init_logger(self) -> None:
        self._logger = logging.getLogger("tmh.audit")
        self._logger.setLevel(logging.INFO)
        # 审计日志自成一体，不向根日志传播，避免混入 app.log / 控制台
        self._logger.propagate = False

        if not self._logger.handlers:
            log_path = PathManager.get_logs_path("audit.log")
            handler = TimedRotatingFileHandler(
                filename=log_path,
                when="midnight",
                backupCount=180,  # 约半年
                encoding="utf-8",
            )
            # 记录内容本身即为完整 JSON，无需再套用普通日志格式
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def record(self, category: str, action: str, result: str, operator: Optional[str], fields: dict) -> None:
        try:
            entry = {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "category": category,
                "action": action,
                "result": result,
                "operator": operator or "system",
            }
            if fields:
                # 过滤掉 None，保持记录整洁
                detail = {k: v for k, v in fields.items() if v is not None}
                if detail:
                    entry["detail"] = detail
            self._logger.info(json.dumps(entry, ensure_ascii=False))
        except Exception:
            # 审计绝不能影响主流程
            logging.getLogger(__name__).exception("写入审计日志失败")


def audit(
    category: str,
    action: str,
    result: str = AuditResult.SUCCESS,
    operator: Optional[str] = None,
    **fields,
) -> None:
    """记录一条审计事件（线程安全，写入失败静默）。

    Args:
        category: 事件分类，见 :class:`AuditCategory`。
        action: 具体动作，如 ``"start"`` / ``"set_flow"``。
        result: 结果，见 :class:`AuditResult`，默认 ``SUCCESS``。
        operator: 操作者（如实验操作员），缺省记为 ``system``。
        **fields: 附加上下文，将作为 ``detail`` 一并记录。
    """
    _AuditLogger().record(category, action, result, operator, fields)
