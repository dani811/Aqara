# Contract: operation catalog & generic builder

Public surface added by feature 010, exported from `aqara_u200_ble`.

## Data

- `CommandFamily` — enum/dataclass of the eight families (`main_cmd`, `name`, `reply`).
- `OperationStatus` — `CONFIRMED` | `CATALOGUED`.
- `OperationEntry` — `family, sub_cmd, name, status, confirmed_frame, note`.
- `OPERATIONS_CATALOG` — the full collection, keyed by `(main_cmd, sub_cmd)`.

## `find_operation(main_cmd: int, sub_cmd: int) -> OperationEntry | None`

- Returns the entry for a family+sub pair, or `None` if not catalogued.
- Never raises on an unknown pair (analysis must not break on an unseen command).

## `operations_in_family(main_cmd: int) -> list[OperationEntry]`

- All catalogued operations of a family, in sub-command order.

## `build_control_frame(main_cmd: int, sub_cmd: int, data: bytes = b"", seq: int = 1) -> bytes`

- Returns the level-3 plaintext `main_cmd + sub_cmd + data`.
- For `SYSTEM 0x74` it MUST equal `build_operate_frame(...)` (the confirmed operate
  frame with its additive trailer); the direction/seq come from `data`/`seq` per
  the documented mapping.
- For other families it emits `main_cmd sub_cmd data` and its docstring states the
  trailer/sequence is **unverified** for non-`0x74` commands.
- Validates byte ranges (`0..255`) and rejects out-of-range input.

## Invariants

- Every `OperationEntry.status == CONFIRMED` has a non-null `confirmed_frame` that
  matches a real capture; `CATALOGUED` entries have `confirmed_frame is None`.
- The catalog covers all eight families present in the decompiled enum.
- No entry actuates anything — building a frame does not send it.

## Reference (confirmed)

`build_operate_frame(open=True, seq=1) == bytes.fromhex("74010100b917")` and the
catalog marks exactly open/close/keepalive as `CONFIRMED`.
