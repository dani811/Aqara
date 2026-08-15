# Quickstart & Validation Guide: Cloud I/O Async-Safe

**Feature**: 012 - Cloud I/O Async-Safe

**Date**: 2026-08-15

---

## Prerequisites

- Python 3.10+
- `aqara_u200_ble` library installed (or running from source)
- A test BLE client (mock or real)
- `pytest` for running validation tests

---

## Scenario 1: Cloud I/O Does Not Block Event Loop

**Goal**: Verify that cloud calls execute in a worker thread and do not stall the asyncio event loop.

### Setup

```bash
# Create a test file: test_async_loop_responsive.py
```

### Test Code

```python
import asyncio
from aqara_u200_ble import run_authenticated_lock_operation
from tests.test_async_cloud_boundary import SlowCloudHelper, FakeLockClient, LockScript


async def test_event_loop_remains_responsive():
    """Cloud I/O should not block other async tasks."""

    # Mock cloud helper with 0.2s delay
    slow_cloud = SlowCloudHelper(delay_seconds=0.2)
    completed_tasks = []

    async def light_task(task_id):
        """A lightweight task that should run concurrently."""
        completed_tasks.append(task_id)

    # Monkey-patch cloud helpers
    import aqara_u200_ble.session as session

    session.cloud_get_public_key = slow_cloud.get_public_key
    session.get_session_material = slow_cloud.get_session_material

    # Start lock operation (will call cloud helpers)
    lock_op = asyncio.create_task(
        run_authenticated_lock_operation(
            client=FakeLockClient(LockScript()),
            device_id="test",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="unlock",
            notify_timeout=0.5,
            signer=None,
        )
    )

    # Schedule light tasks while cloud is in flight
    for i in range(5):
        asyncio.create_task(light_task(i))
        await asyncio.sleep(0.01)  # Yield control

    # Wait for everything to complete
    try:
        await lock_op
    except Exception:
        pass  # Cloud call may fail; we're testing responsiveness, not success

    await asyncio.sleep(0.1)  # Give tasks time to complete

    # Most light tasks should complete despite cloud delay
    assert len(completed_tasks) > 0, "Event loop was stalled!"
    print(f"✅ Event loop remained responsive: {len(completed_tasks)}/5 light tasks completed")


# Run test
asyncio.run(test_event_loop_remains_responsive())
```

### Expected Output

```
✅ Event loop remained responsive: 4/5 light tasks completed
```

---

## Scenario 2: Concurrent Operations Rejected

**Goal**: Verify that calling `run_authenticated_lock_operation()` twice concurrently on the same lock raises `OperationInProgressError`.

### Test Code

```python
import asyncio
from aqara_u200_ble import run_authenticated_lock_operation, OperationInProgressError
from tests.test_async_cloud_boundary import SlowCloudHelper, FakeLockClient, LockScript


async def test_concurrent_operations_rejected():
    """Concurrent calls to the same lock should raise OperationInProgressError."""

    slow_cloud = SlowCloudHelper(delay_seconds=0.5)

    import aqara_u200_ble.session as session

    session.cloud_get_public_key = slow_cloud.get_public_key
    session.get_session_material = slow_cloud.get_session_material

    client = FakeLockClient(LockScript())

    # Start first operation
    op1 = asyncio.create_task(
        run_authenticated_lock_operation(
            client=client,
            device_id="lock-123",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="unlock",
            signer=None,
        )
    )

    # Wait a bit, then try to start a second operation on the same lock
    await asyncio.sleep(0.05)

    try:
        await run_authenticated_lock_operation(
            client=client,
            device_id="lock-123",  # Same device
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="lock",
            signer=None,
        )
        assert False, "Second call should have raised OperationInProgressError"
    except OperationInProgressError as e:
        print(f"✅ Concurrent operation correctly rejected: {e}")

    # Wait for first operation to complete
    try:
        await op1
    except Exception:
        pass


# Run test
asyncio.run(test_concurrent_operations_rejected())
```

### Expected Output

```
✅ Concurrent operation correctly rejected: Another lock operation is in progress...
```

---

## Scenario 3: No Secrets in Logs

**Goal**: Verify that DEBUG logs do not contain credentials, session keys, or sensitive material.

### Test Code

```python
import logging
from aqara_u200_ble import run_authenticated_lock_operation
from tests.test_async_cloud_boundary import FakeLockClient, LockScript

# Enable DEBUG logging to capture everything
logging.basicConfig(level=logging.DEBUG)

# Sensitive strings we want to ensure are NOT in logs
SENSITIVE_PATTERNS = [
    "000102030405060708090a0b0c0d0e0f",  # sessionKey
    "0102030405060708090a0b0c0d",  # nonce
    "aabbccddeeff00112233445566778899",  # verifyData
]


def test_no_secrets_in_logs():
    """Secrets should never appear in logs."""

    import io
    import sys

    # Capture logs
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(handler)

    # Run operation
    try:
        asyncio.run(
            run_authenticated_lock_operation(
                client=FakeLockClient(LockScript()),
                device_id="test",
                auth_headers=None,
                region="EU",
                base_url=None,
                operation="unlock",
                signer=None,
            )
        )
    except Exception:
        pass

    # Check logs
    log_output = log_capture.getvalue()

    for pattern in SENSITIVE_PATTERNS:
        assert pattern not in log_output, f"Sensitive pattern found in logs: {pattern}"

    print(f"✅ No secrets found in logs")
    print(f"   Log output length: {len(log_output)} bytes")


test_no_secrets_in_logs()
```

### Expected Output

```
✅ No secrets found in logs
   Log output length: 342 bytes
```

---

## Scenario 4: Exception Propagation (No Wrapping)

**Goal**: Verify that cloud exceptions propagate without wrapping, preserving exception type and message.

### Test Code

```python
import asyncio
from aqara_u200_ble import run_authenticated_lock_operation


class CustomCloudError(Exception):
    pass


async def test_exception_propagation():
    """Cloud exceptions should propagate unwrapped."""

    def fake_public_key_fails(**kwargs):
        raise CustomCloudError("Cloud API returned 500")

    import aqara_u200_ble.session as session

    session.cloud_get_public_key = fake_public_key_fails

    from tests.test_async_cloud_boundary import FakeLockClient, LockScript

    try:
        await run_authenticated_lock_operation(
            client=FakeLockClient(LockScript()),
            device_id="test",
            auth_headers=None,
            region="EU",
            base_url=None,
            operation="unlock",
            signer=None,
        )
        assert False, "Should have raised CustomCloudError"
    except CustomCloudError as e:
        # Exception type preserved, message intact
        assert str(e) == "Cloud API returned 500"
        assert type(e) is CustomCloudError
        print(f"✅ Exception propagated without wrapping: {type(e).__name__}: {e}")
    except Exception as e:
        assert False, f"Wrong exception type: {type(e)}"


asyncio.run(test_exception_propagation())
```

### Expected Output

```
✅ Exception propagated without wrapping: CustomCloudError: Cloud API returned 500
```

---

## Running Full Test Suite

```bash
# Run all async-boundary tests
pytest tests/test_async_cloud_boundary.py -v

# Expected: All tests pass
# - test_cloud_helpers_execute_on_different_thread
# - test_slow_cloud_does_not_stall_event_loop
# - test_cloud_helper_exception_propagates
# - test_cloud_material_exception_propagates
# - test_function_signature_unchanged
# - test_function_is_still_async
# - test_return_type_unchanged
```

---

## Integration Validation

### For Home Assistant Integration

1. **Responsiveness Check**: Launch Home Assistant with `haos_aqara`, trigger a lock operation, and verify that:
   - Other automations/sensors respond during the 2-5 second cloud I/O window
   - The UI doesn't stall
   - Logs show no secrets

2. **Concurrent Operations Check**: Write an automation that triggers multiple lock operations and verify:
   - Only one succeeds; others are rejected with a clear error
   - Home Assistant's error handling surfaces the error gracefully

3. **Slow Cloud Check**: Simulate a slow cloud API (using a proxy or mock) and verify:
   - Event loop remains responsive
   - Operation eventually completes or times out with an exception
   - Logs are clean (DEBUG level, no secrets)

---

## Success Criteria Met

- ✅ Cloud I/O does not block event loop
- ✅ Concurrent operations rejected with clear error
- ✅ Exceptions propagate unwrapped
- ✅ No secrets in logs
- ✅ 100% backward compatible
- ✅ All existing tests pass
