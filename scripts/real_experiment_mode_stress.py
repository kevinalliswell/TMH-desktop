#!/usr/bin/env python3
"""Real-hardware stress test for the experiment start/stop flow.

This script intentionally exercises the application runtime path while staying
inside the first GB/T 13242 stage: N2=5.0 L/min, CO/CO2/H2=0.0. It is meant for
shop-floor verification after serial ports and devices are connected.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infrastructure.repositories import CommConfigRepository  # noqa: E402
from src.models.experiment_state import ExperimentPhase  # noqa: E402
from src.services.app_runtime import AppRuntime  # noqa: E402
from src.utils.path_manager import PathManager  # noqa: E402


DEFAULT_RELEASE_CONFIG = (
    ROOT
    / "release"
    / "TMH_1.5.260625_windows_amd64_20260625_191731"
    / "TMH"
    / "configs"
    / "comm_config.json"
)

MODE_ID = "GB_13242_2017"
SAFETY_SETPOINTS = {
    "H2": 0.0,
    "N2": 5.0,
    "CO2": 0.0,
    "CO": 0.0,
}


def _patch_paths(config_dir: Path, data_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    def get_config_path(filename=None):
        return str(config_dir / filename) if filename else str(config_dir)

    def get_data_path(filename=None):
        return str(data_dir / filename) if filename else str(data_dir)

    PathManager.get_config_path = staticmethod(get_config_path)
    PathManager.get_data_path = staticmethod(get_data_path)


def _write_exp_settings(config_dir: Path, cycle: int) -> None:
    settings = {
        "project_name": f"Real Stress {cycle:03d}",
        "sample_name": "Real Device Stress",
        "sample_id": f"REAL-STRESS-{cycle:03d}",
        "experiment_type": "GB/T 13242-2017 铁矿石低温粉化试验方法",
        "experiment_mode_id": MODE_ID,
        "sample_weight": 523.0,
        "operator": "codex",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": "real hardware first-stage start/stop stress test",
    }
    (config_dir / "exp_settings.config").write_text(
        json.dumps(settings, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def _copy_comm_config(source: Path, config_dir: Path) -> None:
    target = config_dir / "comm_config.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _process_events(duration_s: float) -> None:
    end = time.time() + duration_s
    while time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.05)


def _summarize_status(runtime: AppRuntime) -> dict:
    services = runtime.services
    status = services.device_hub.get_all_status()
    snapshots = services.device_hub.get_snapshots()
    legacy = services.device_hub.get_status_legacy()
    frames = legacy.get("frames") or {}

    temp = status.get("Temp", {}).get("data") or {}
    balance = status.get("Balance", {}).get("data") or {}
    mfc_snapshot = snapshots.devices.get("MFC") if snapshots else None
    mfc_channels = (mfc_snapshot.payload.get("channels") if mfc_snapshot else {}) or {}

    flow_frames = frames.get("flows") or {}
    flow_summary = {}
    for gas in ("H2", "N2", "CO2", "CO"):
        payload = getattr(flow_frames.get(gas), "payload", {}) or {}
        flow_summary[gas] = {
            "pv": payload.get("pv", mfc_channels.get(gas, {}).get("pv")),
            "sv": payload.get("sv", mfc_channels.get(gas, {}).get("sv")),
        }

    return {
        "temp_T8": temp.get("T8"),
        "weight": balance.get("weight"),
        "flows": flow_summary,
        "status": {
            name: {
                "running": values.get("running"),
                "connected": values.get("connected"),
                "last_update_ts": values.get("last_update_ts"),
                "error_message": values.get("error_message"),
            }
            for name, values in status.items()
        },
    }


def _wait_for_devices(runtime: AppRuntime, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _summarize_status(runtime)
        status = summary["status"]
        temp_ok = status.get("Temp", {}).get("last_update_ts") is not None
        balance_ok = status.get("Balance", {}).get("last_update_ts") is not None
        mfc_ok = status.get("MFC", {}).get("last_update_ts") is not None
        if temp_ok and balance_ok and mfc_ok:
            return True
        _process_events(0.2)
    return False


def _set_protective_gas(runtime: AppRuntime) -> dict[str, bool]:
    device_manager = runtime.services.device_manager
    results = {}
    for gas, flow in SAFETY_SETPOINTS.items():
        results[gas] = bool(device_manager.set_flow(gas, flow))
        time.sleep(0.08)
    return results


def _count_experiments(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]


def run(args: argparse.Namespace) -> int:
    app = QCoreApplication.instance() or QCoreApplication([])
    config_source = Path(args.config).resolve()
    config_dir = Path(args.work_dir).resolve() / "configs"
    data_dir = Path(args.work_dir).resolve() / "data"
    _patch_paths(config_dir, data_dir)
    _copy_comm_config(config_source, config_dir)
    _write_exp_settings(config_dir, 0)

    print(f"CONFIG_SOURCE={config_source}")
    print(f"WORK_DIR={Path(args.work_dir).resolve()}")
    print(f"CYCLES={args.cycles} HOLD_SECONDS={args.hold_seconds}")

    runtime = AppRuntime(
        save_interval=1,
        comm_config_repository=CommConfigRepository(str(config_dir / "comm_config.json")),
    )
    controller = None
    failures: list[str] = []

    try:
        runtime.start()
        _process_events(args.warmup_seconds)
        if not _wait_for_devices(runtime, timeout_s=args.device_timeout):
            failures.append("device data timeout")

        print(f"DEVICE_BACKENDS={runtime.services.device_backend_sources}")
        print(f"INITIAL_SUMMARY={json.dumps(_summarize_status(runtime), ensure_ascii=False)}")

        controller = runtime.services.experiment_runtime.ensure_controller()
        for cycle in range(1, args.cycles + 1):
            _write_exp_settings(config_dir, cycle)
            print(f"\n--- CYCLE {cycle}/{args.cycles} ---")

            if not controller.set_experiment_mode_by_id(MODE_ID):
                failures.append(f"cycle {cycle}: set mode failed")
                break
            if not controller.start_experiment():
                failures.append(f"cycle {cycle}: start failed")
                break

            _process_events(args.hold_seconds)
            running_state = controller.state_machine.get_state()
            print(
                "RUNNING_STATE="
                f"phase={running_state.phase.name}, "
                f"stage={running_state.current_stage_index + 1}/{running_state.total_stages}, "
                f"timer={controller.stage_timer.isActive()}"
            )
            print(f"RUNNING_SUMMARY={json.dumps(_summarize_status(runtime), ensure_ascii=False)}")

            if not controller.stop_experiment():
                failures.append(f"cycle {cycle}: stop failed")
                break

            _process_events(args.between_cycles_seconds)
            safety_results = _set_protective_gas(runtime)
            stopped_state = controller.state_machine.get_state()
            final_summary = _summarize_status(runtime)
            print(
                "STOPPED_STATE="
                f"phase={stopped_state.phase.name}, "
                f"running={controller.is_experiment_running()}, "
                f"stage_timer={controller.stage_timer.isActive()}, "
                f"duration_timer={controller.experiment_duration_updater.isActive()}"
            )
            print(f"SAFETY_RESULTS={safety_results}")
            print(f"STOPPED_SUMMARY={json.dumps(final_summary, ensure_ascii=False)}")

            if stopped_state.phase != ExperimentPhase.IDLE:
                failures.append(f"cycle {cycle}: state not idle")
                break
            if controller.stage_timer.isActive() or controller.experiment_duration_updater.isActive():
                failures.append(f"cycle {cycle}: timer still active")
                break
            if not all(safety_results.values()):
                failures.append(f"cycle {cycle}: protective gas command failed")
                break

        if controller and controller.is_experiment_running():
            controller.stop_experiment()
        _set_protective_gas(runtime)
        _process_events(0.5)

        db_path = data_dir / "experiments.db"
        created = _count_experiments(db_path)
        print(f"\nEXPERIMENT_DB={db_path}")
        print(f"EXPERIMENT_RECORDS={created}")

        if failures:
            print(f"RESULT=FAIL failures={failures}")
            return 1
        print("RESULT=PASS")
        return 0
    finally:
        try:
            if controller and controller.is_experiment_running():
                controller.stop_experiment()
        except Exception as exc:
            print(f"WARN stop_experiment cleanup failed: {exc}")
        try:
            if runtime.is_started:
                _set_protective_gas(runtime)
        except Exception as exc:
            print(f"WARN protective gas cleanup failed: {exc}")
        runtime.stop()
        _process_events(0.2)
        app.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_RELEASE_CONFIG))
    parser.add_argument("--work-dir", default=str(ROOT / "tmp" / "real_experiment_stress"))
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--between-cycles-seconds", type=float, default=0.8)
    parser.add_argument("--warmup-seconds", type=float, default=2.0)
    parser.add_argument("--device-timeout", type=float, default=8.0)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
