# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and release tags follow `v<version>`.

## [Unreleased]

### Added

- GitHub Actions CI workflow with smoke-test coverage for repository health checks.
- Tag-driven GitHub Release workflow for Windows packaging and asset publishing.
- GitHub issue forms, pull request template, CODEOWNERS, Dependabot, and release-note categories.
- Stable `tests/ci` smoke suite and version validation script for automation.

### Changed

- Standardized repository workflow around `main`, `develop`, feature, bugfix, hotfix, and release branches.
- Updated developer setup instructions to install the local `tmh_comm` package using a build-compatible path install.
- Clarified the active Python baseline for automated validation.

## [1.1.251121] - 2025-11-21

### Changed

- 重构通信设置页面：控件引用集中管理、信号连接分离、串口刷新、恢复默认、脏状态跟踪。
- 优化设备客户端：移除冗余协议文件，统一使用 `tmh_comm` 协议包。

