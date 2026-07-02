"""CI tests for the system audit log (#34)."""
from __future__ import annotations

import json
import logging


def _flush_audit():
    for h in logging.getLogger("tmh.audit").handlers:
        h.flush()


def _last_audit_entries(n=5):
    from src.utils.path_manager import PathManager

    with open(PathManager.get_logs_path("audit.log"), encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()[-n:] if line.strip()]


def test_audit_writes_structured_json_entry():
    from src.utils.audit import audit, AuditCategory

    marker = "unit-test-exp-42"
    audit(AuditCategory.EXPERIMENT, "start", operator="tester", experiment_id=marker, mode="GB_13241")
    _flush_audit()

    entry = next(e for e in _last_audit_entries() if e.get("detail", {}).get("experiment_id") == marker)
    assert entry["category"] == "EXPERIMENT"
    assert entry["action"] == "start"
    assert entry["result"] == "SUCCESS"
    assert entry["operator"] == "tester"
    assert entry["detail"]["mode"] == "GB_13241"
    assert "ts" in entry


def test_audit_defaults_operator_and_drops_none_fields():
    from src.utils.audit import audit, AuditCategory, AuditResult

    audit(AuditCategory.AUTH, "verify_password", result=AuditResult.FAILURE, note=None, tag="u-t-none")
    _flush_audit()

    entry = next(e for e in _last_audit_entries() if e.get("detail", {}).get("tag") == "u-t-none")
    assert entry["operator"] == "system"       # default when not provided
    assert entry["result"] == "FAILURE"
    assert "note" not in entry.get("detail", {})  # None values are filtered out


def test_audit_never_raises_on_bad_input():
    from src.utils.audit import audit, AuditCategory

    class Unserializable:
        pass

    # A value json cannot serialize must not propagate an exception to the caller.
    audit(AuditCategory.APP, "start", weird=Unserializable())
