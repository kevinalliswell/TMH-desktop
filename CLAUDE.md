# TMH-LPF-900

Iron ore metallurgical performance integrated testing and control system, developed at USTB (University of Science and Technology Beijing). PySide6 desktop application for temperature control (9-channel), gas mass flow control (H2/N2/CO2/CO via MFC), and electronic balance measurement, conforming to Chinese national standards GB/T 13240, 13241, 13242.

## Quick Reference

```bash
# Install dependencies
pip install -r requirements-dev.txt ./packages/tmh_comm

# Run application
python src/app.py

# Run CI tests (headless)
QT_QPA_PLATFORM=offscreen PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest

# Compile check (no execution)
python -m compileall src packages/tmh_comm/src scripts tests/ci

# Verify release metadata
python scripts/release_manager.py verify
```

## Commit Conventions

Conventional Commits with scope: `feat(ui):`, `fix(device):`, `refactor(services):`, `test(ci):`, `chore(release):`, `docs:`.

- English in code, comments, and commit messages
- Chinese in UI strings, log messages, and user-facing documentation

## Branch Strategy (Gitflow)

- `main` — production, tagged releases only
- `develop` — integration branch
- `feature/*`, `bugfix/*`, `hotfix/*`, `release/*` — from develop (hotfix from main)
- Squash-merge PRs

## Architecture

Transitioning to layered architecture (see `docs/架构重构蓝图.md`):

```
UI (PySide6 pages/widgets/dialogs)
  -> Presenters / UI Adapters
    -> Application Services (use cases, orchestration)
      -> Domain (pure Python, no Qt — state machine, business rules)
        -> Infrastructure Adapters (DB, file, config, device bridges)
```

Key directories:
- `src/domain/` — Pure Python domain model (ExperimentStateMachineCore)
- `src/application/` — DTOs, ports (Protocol interfaces), application services
- `src/infrastructure/` — Concrete adapters (DeviceHubAdapter, CommConfigRepository, device bridges)
- `src/controllers/` — ExperimentController (QObject, experiment lifecycle)
- `src/services/` — AppRuntime (composition root), database, experiment modes, GB calculators
- `src/device_clients/` — Device drivers (BaseDevice, DeviceManager, MFC/Temp/Balance clients)
- `src/ui/` — MainWindow, pages, dialogs, presenters, UI adapters
- `src/utils/` — Logger, PathManager, PasswordManager
- `packages/tmh_comm/` — Local pip package for device communication protocols (Modbus-CPL, Modbus-RTU, RS232-ASCII)

## Key Conventions

- **Version source of truth:** `configs/software.info`
- **Logging:** Use `from src.utils.logger import get_logger` — never use `print()` for diagnostics
- **Paths:** Use `PathManager` — never construct file paths manually
- **Config files:** `configs/`, data: `data/`, exports: `exports/`, logs: `logs/`
- **Dependency injection:** Factory-based DI in `AppRuntime` (`src/services/app_runtime.py`)

## Testing

- CI runs only `tests/ci/` (pytest with `QT_QPA_PLATFORM=offscreen`)
- Hardware/UI integration tests under `tests/` root are manual-only
- `conftest.py` patches `sys.path` and sets offscreen rendering
- CI uses Python 3.12 on ubuntu-latest

## Constraints

- Do NOT import Qt types in `src/domain/` or `src/application/` layers
- New code should import ExperimentController from `src.controllers.experiment_controller`
- `configs/exp_settings.config` is the live experiment settings file
- Device communication goes through `tmh_comm` protocol library, not pymodbus
