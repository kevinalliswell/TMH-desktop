# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and release tags follow `v<version>`.

## [Unreleased]

## [1.6.260702] - 2026-07-02

### Added

- Single-instance guard: only one application instance may run at a time, so a
  second launch cannot fight over the exclusive serial ports / device buses.
  Uses QLockFile with owner PID/host recording and stale-lock recovery (#26).
- System audit log: key operations (app start/exit, experiment start/stop/
  complete/mode change, gas setpoint, balance tare, data export/report,
  password verify/change) are recorded as structured JSON in a dedicated,
  daily-rotating logs/audit.log (#34).

### Fixed

- GB/T 13241 reduction degree: oxygen content is now treated as a percentage,
  fixing a result that was 100x too small (#41).
- Temperature read failures no longer masquerade as success (all-None dict was
  truthy), so disconnects are detected and reconnect is triggered (#42).
- Live charts: the shared time axis is advanced once per frame, fixing X-axis
  corruption of the temperature/flow/weight curves (#43).
- Flammable-gas (H2/CO) safety clamp is now enforced on the external MFC package
  path, not only the legacy client (#44).
- MFC CPL responses with real device framing (ETX + checksum + CRLF) now parse
  correctly instead of returning None (#45).
- database.repair_database commits before VACUUM so the repair no longer fails (#46).
- experiment_type_manager returns standard-type stages via get_experiment_stages
  instead of a missing method that silently returned an empty list (#47).
- Switching from a custom experiment mode back to a standard mode clears the
  stale custom-type state (#48).
- Empty 备注/notes no longer blocks starting an experiment (#49).
- Balance weight of None no longer drops experiment data points (#50).
- Balance client tracks health and reconnects after a mid-session disconnect (#51).
- experiment_data dataclasses import correctly (dataclass field ordering) (#40).
- Chart legends now populate (legend is created before the curves); About page
  shows the real version; minor cleanups (Qt stylesheet, fallback ids, logs).

## [1.5.260625] - 2026-06-25

### Fixed

- Balance tare now propagates the real device command result through the experiment
  controller, so the UI no longer reports success or resets the initial weight when
  the instrument does not confirm the tare command.
- Manual balance tare and initial-weight actions now prepare the experiment controller
  with UI interaction callbacks before sending device commands, preserving the
  confirmation dialog even before an experiment has been initialized.
- Balance serial reads are now synchronized between the background acquisition thread
  and tare commands, preventing the acquisition loop from consuming the instrument's
  tare acknowledgement during UI button operation.
- Added CI coverage for balance tare response parsing, controller failure handling,
  presenter-side controller preparation, and tare command serial locking.

## [1.4.260625] - 2026-06-25

### Changed

- Manual gas control panel now caps H2/CO input at the configured safety limit and
  refreshes the cap after the limit is changed and applied (previously fixed at 5 L/min).
- Device communication status is shown only in the status bar; the duplicate
  title-bar indicator was removed.

### Fixed

- Temperature controller: locate the CRC-valid Modbus `0x03` response frame and skip any
  echoed request / line noise from half-duplex RS485 adapters (such echo was previously
  mis-parsed as an all-empty reading). Raw bytes are now logged when no valid frame is
  found, to aid field diagnosis.

### Documentation

- Add the field commissioning & installation guide (`docs/现场调试与装机说明.md`).

## [1.3.260625] - 2026-06-25

### Added

- Configurable flammable-gas (H2/CO) flow upper limits (`GAS_SAFETY_LIMITS` in the
  communication config, default 5 L/min each), editable only after admin-password
  unlock on the communication settings page.
- Device communication self-test: `scripts/comm_selftest.py` field-commissioning CLI
  (MFC/Temp/Balance, with a Modbus address scan), and an in-app "测试连接" button on
  the communication settings page reporting per-device connection status.

### Changed

- CI now runs the smoke suite on Windows in addition to Ubuntu.
- Pin dependency upper bounds to guard against silent major-version breakage; route
  Dependabot updates to `develop` and ignore the pandas 3.x major bump.

### Security

- Enforce the H2/CO flow upper limits as a hard clamp before any setpoint is written
  to the MFC — covering manual control, experiment stages, and programmatic calls.
  Manual-panel and stage-editor input ranges are synced to the configured limit.

### Removed

- Stop tracking runtime data, generated exports, and developer working notes; archive
  retrospective development-log docs under `docs/dev-notes/`.

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
