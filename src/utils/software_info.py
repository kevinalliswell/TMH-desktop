"""Load release metadata from the repository's single source of truth."""

from __future__ import annotations

import json
from pathlib import Path

from src.utils.path_manager import PathManager


DEFAULT_SOFTWARE_INFO = {
    "version": "unknown",
    "author": "北京科技大学",
    "release_date": "",
    "copyright": "© 北京科技大学",
    "description": "TMH-LPF-900 铁矿石冶金性能综合检测与控制系统",
    "contact": "",
    "website": "",
}


def load_software_info(info_path: str | Path | None = None) -> dict:
    """Return configured metadata merged over one shared safe fallback."""
    path = Path(info_path or PathManager.get_config_path("software.info"))
    try:
        configured = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(configured, dict):
            raise TypeError("software.info must contain a JSON object")
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_SOFTWARE_INFO.copy()

    return {**DEFAULT_SOFTWARE_INFO, **configured}
