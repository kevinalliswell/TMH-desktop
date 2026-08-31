"""A setpoint queued behind a slow read must not be reported as a device fault.

``_wait_for_command`` sized its dispatch wait from the NEW command's own
timeout (3 s for a write) while one in-flight read can hold the executor for the
whole retry window (~15.6 s with the shipped config, because PERFORMANCE_CONFIG
has no connection_timeout key and COMMAND_TIMEOUT falls back to 5.0). Priority
does not help: the processor is inside the previous command, not waiting on
queue.get().

The write was therefore cancelled and reported as failure on healthy hardware,
which the stage logic escalated into '阶段气体设定失败，实验已中止' — and on the
exit path made the safety purge fail, so the window refused to close.
"""
import threading

import pytest

from src.device_clients.multi_mfc_client import (
    CommandPriority,
    MultiMFCClient,
    SerialCommand,
)


class _Client:
    """Bare MultiMFCClient with only the timing knobs the budget math reads."""

    MAX_RETRIES = MultiMFCClient.MAX_RETRIES
    RETRY_DELAY = MultiMFCClient.RETRY_DELAY
    COMMAND_TIMEOUT = 5.0  # what the shipped config actually produces
    WRITE_COMMAND_TIMEOUT = MultiMFCClient.WRITE_COMMAND_TIMEOUT

    _worst_case_execution_time = MultiMFCClient._worst_case_execution_time
    _queue_wait_timeout = MultiMFCClient._queue_wait_timeout
    _command_execution_timeout = MultiMFCClient._command_execution_timeout


def test_queue_wait_covers_a_full_in_flight_command():
    client = _Client()
    write = SerialCommand(b"cmd", CommandPriority.HIGH, timeout=client.WRITE_COMMAND_TIMEOUT)

    in_flight_worst_case = client._worst_case_execution_time(client.COMMAND_TIMEOUT)
    queue_wait = client._queue_wait_timeout(write)

    assert queue_wait >= in_flight_worst_case, (
        f"排队等待 {queue_wait:.2f}s 短于在途命令最坏占用 {in_flight_worst_case:.2f}s，"
        "健康硬件上的写命令会被误判为设备故障"
    )


def test_queue_wait_is_not_the_commands_own_timeout():
    """The old sizing: max(1.0, command.timeout) == 3.0 for a write."""
    client = _Client()
    write = SerialCommand(b"cmd", CommandPriority.HIGH, timeout=3.0)

    assert client._queue_wait_timeout(write) > 3.0


def test_execution_window_still_covers_every_retry():
    client = _Client()
    read = SerialCommand(b"cmd", CommandPriority.NORMAL, timeout=5.0)

    # 3 attempts x (5.0 + 0.1) + 2 x 0.2 + 0.25
    assert client._command_execution_timeout(read) == pytest.approx(15.95)


# --- dispatch failure is distinguishable from a silent device ---------------


def _command_never_dispatched(client):
    command = SerialCommand(b"cmd", CommandPriority.HIGH, timeout=0.01)
    MultiMFCClient._wait_for_command(client, command)
    return command


class _FastClient(_Client):
    COMMAND_TIMEOUT = 0.01
    WRITE_COMMAND_TIMEOUT = 0.01
    MAX_RETRIES = 1
    RETRY_DELAY = 0.0

    def __init__(self):
        import logging

        self.logger = logging.getLogger("queue-budget-test")


def test_undispatched_command_is_flagged_as_such():
    command = _command_never_dispatched(_FastClient())

    assert command.dispatch_failed is True
    assert command.cancelled.is_set()


def test_dispatched_but_unanswered_command_is_not_a_dispatch_failure():
    client = _FastClient()
    command = SerialCommand(b"cmd", CommandPriority.HIGH, timeout=0.01)
    command.started.set()  # the executor picked it up; the device stayed silent

    assert MultiMFCClient._wait_for_command(client, command) is False
    assert command.dispatch_failed is False


def test_cancelling_pending_commands_releases_waiters():
    client = _FastClient()
    from queue import PriorityQueue

    client._command_queue = PriorityQueue()
    queued = SerialCommand(b"cmd", CommandPriority.HIGH, timeout=0.01)
    client._command_queue.put((0, queued))

    released = threading.Event()

    def _wait():
        queued.completed.wait(timeout=2.0)
        released.set()

    waiter = threading.Thread(target=_wait, daemon=True)
    waiter.start()

    MultiMFCClient._cancel_pending_commands(client)

    assert released.wait(timeout=2.0) is True, "关停时排队命令必须释放等待方而非静默丢弃"
    assert queued.cancelled.is_set()
    waiter.join(timeout=2.0)
