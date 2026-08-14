# Quickstart: operation catalog & builder

## 1. Browse the catalog (no lock, no network)

```python
from aqara_u200_ble import OPERATIONS_CATALOG, operations_in_family, find_operation

# Everything in the SYSTEM family:
for entry in operations_in_family(0x01):
    print(f"{entry.sub_cmd:#04x} {entry.name} [{entry.status.value}]")

# Look up one operation:
print(find_operation(0x01, 0x74))   # BLE_OPEN_LOCK, CONFIRMED
print(find_operation(0x01, 0x02))   # SET_VOLUME, CATALOGUED
```

## 2. Confirm the builder reproduces the verified commands

```bash
.venv/bin/python -m pytest tests/test_operations_catalog.py -q
```

Expected: green. Includes a test that
`build_operate_frame(open=True, seq=1) == 74010100b917` and that the generic
`build_control_frame` agrees with the confirmed operate frame.

## 3. Build a frame for any operation

```python
from aqara_u200_ble import build_control_frame

# Generic level-3 command (mainCmd subCmd data):
frame = build_control_frame(0x01, 0xe5)          # GET_DOOR_LOCK_STATUS, empty data
# Confirmed operate frame stays exact:
from aqara_u200_ble import build_operate_frame
assert build_operate_frame(open=True).hex() == "74010100b917"
```

> Building a frame does **not** send it. Driving a `catalogued` operation against
> the lock is out of scope for this feature until its exact data is confirmed.

## 4. Promote a catalogued command to confirmed

To recover an operation's exact `data`, capture it live (the feature-009 method):

1. Reinstall the Frida-gadget app (`specs/009-lock-open-spike`), launch it frozen,
   attach Frida on `127.0.0.1:27042`.
2. Hook `AqEdUtils.encryptAESCCM`; perform the operation once in the app.
3. Read the plaintext `mainCmd subCmd data` from the hook, and update the catalog
   entry's `confirmed_frame` + status.

Alternatively, read the operation's builder in the app bundle
(`sendAddPasswordCmd`, `autoLockTimeCmd`, …) for the data structure.
