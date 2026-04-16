# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and release tags follow `v<version>`.

## [Unreleased]

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
