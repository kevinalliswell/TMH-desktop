"""Architecture guardrails from CLAUDE.md, enforced in CI.

- ``src/domain`` and ``src/application`` must stay Qt-free (pure Python).
- Device communication must go through ``tmh_comm``, never pymodbus.
- Diagnostics under ``src`` must use the application logger, never ``print``.

The checks scan source text instead of importing modules so a violation is
reported with its file and line even when the offending module cannot be
imported in a headless environment.
"""
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

QT_IMPORT = re.compile(r"^\s*(?:import|from)\s+(?:PySide6|PyQt5|PyQt6|shiboken6|qtpy)\b")
PYMODBUS_IMPORT = re.compile(r"^\s*(?:import|from)\s+pymodbus\b")


def _violations(root: Path, pattern: re.Pattern) -> list[str]:
    found = []
    for py in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.match(line):
                found.append(f"{py.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")
    return found


def test_domain_layer_is_qt_free():
    assert _violations(PROJECT_ROOT / "src" / "domain", QT_IMPORT) == []


def test_application_layer_is_qt_free():
    assert _violations(PROJECT_ROOT / "src" / "application", QT_IMPORT) == []


def test_no_pymodbus_imports():
    for root in (PROJECT_ROOT / "src", PROJECT_ROOT / "packages" / "tmh_comm" / "src"):
        assert _violations(root, PYMODBUS_IMPORT) == []


def test_source_diagnostics_do_not_use_print():
    violations = []
    for path in sorted((PROJECT_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []
