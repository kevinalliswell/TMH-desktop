# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and release tags follow `v<version>`.

## [Unreleased]

### Added

- Configurable flammable-gas (H2/CO) flow upper limits (`GAS_SAFETY_LIMITS` in the
  communication config, default 5 L/min each), editable only after admin-password
  unlock on the communication settings page.

### Security

- Enforce the H2/CO flow upper limits as a hard clamp before any setpoint is written
  to the MFC — covering manual control, experiment stages, and programmatic calls.
  Manual-panel and stage-editor input ranges are synced to the configured limit.

## [1.2.260624] - 2026-06-24

### Added

- Layered UI architecture: introduced `src/ui/presenters/` (e.g. `ExperimentControlPresenter`) to separate presentation logic from widgets (#6).
- New CI test suites covering the experiment state machine, history-query services, and the device package registry (#6).

### Changed

- Refactored `history_query_page.py` and `integrated_control_page.py` to delegate business logic to services/presenters, substantially reducing widget complexity (#6).
- Extracted hardcoded values into named constants (safety N2 flow, ambient temperature, data queue/buffer sizes) (#12).
- Deferred `PathManager` path resolution from module-import time to runtime to avoid import-time side effects (#12).
- Replaced production-path `print()` calls with structured logger calls across UI and service modules (#12).
- Corrected the README dependency table to list the local `tmh_comm` protocol package instead of the unused `pymodbus` (#12).

### Security

- Replaced plaintext password storage with salted PBKDF2-HMAC-SHA256 (600k iterations) hashing and constant-time comparison; existing plaintext configs auto-migrate on first load (#12).

### Fixed

- Replaced bare `except` clauses with specific exception types in device-client and dialog code (#12).
- Replaced a blocking `time.sleep()` on the Qt main thread with an event-loop pump during initial-weight capture (#12).

### Removed

- Deleted the orphaned `configs/exp_settings.configs` and the dead `ExpSettings` class, and removed the backward-compatibility controller re-export shim (#12).

## [1.1.260416] - 2026-04-16

### Added

- Release preparation script to synchronize `configs/software.info` with `CHANGELOG.md`.

### Changed

- CI and Release workflows now verify full version consistency instead of only checking the raw version string.
- README no longer duplicates release history; `CHANGELOG.md` is now the single release-history document.

## [1.1.251121] - 2025-11-21

### Changed

- 重构通信设置页面：控件引用集中管理、信号连接分离、串口刷新、恢复默认、脏状态跟踪。
- 优化设备客户端：移除冗余协议文件，统一使用 `tmh_comm` 协议包。
