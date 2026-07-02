"""CI test for the single-instance guard (issue #26)."""
import os

from src.utils.single_instance import acquire_single_instance_lock, lock_file_path


def test_second_instance_is_refused_then_reacquirable():
    app_id = f"TMH-test-{os.getpid()}"
    path = lock_file_path(app_id)
    if os.path.exists(path):
        os.remove(path)

    first = acquire_single_instance_lock(app_id)
    assert first is not None, "first instance should acquire the lock"
    try:
        second = acquire_single_instance_lock(app_id)
        assert second is None, "a second instance must be refused while the first holds the lock"
    finally:
        first.unlock()

    # After the holder releases, a fresh launch can acquire again.
    third = acquire_single_instance_lock(app_id)
    assert third is not None, "lock should be re-acquirable once released"
    third.unlock()
    try:
        os.remove(path)
    except OSError:
        pass


def test_lock_file_path_is_stable_and_app_specific():
    assert lock_file_path("foo").endswith("foo.lock")
    assert lock_file_path("a") != lock_file_path("b")
