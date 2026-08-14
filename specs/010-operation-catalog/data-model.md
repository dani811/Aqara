# Phase 1 Data Model: Lock operation & settings catalog

## CommandFamily

The first frame byte and its reply byte.

| Field | Type | Notes |
|-------|------|-------|
| `main_cmd` | int (1 byte) | `01` SYSTEM … `3f` LONG |
| `name` | str | SYSTEM, USER, LOG, ALARM, DEVICELOG, XXQ, SYSTEM_EXT, LONG |
| `reply` | int (1 byte) | `main_cmd | 0x80` (except families with no reply) |

## Status

| Value | Meaning |
|-------|---------|
| `confirmed` | verified against the real lock (feature 009 captures) |
| `catalogued` | from the decompiled enum; exact `data` unverified |

## OperationEntry

| Field | Type | Notes |
|-------|------|-------|
| `family` | CommandFamily | which family this belongs to |
| `sub_cmd` | int (1 byte) | operation selector within the family |
| `name` | str | human-readable (e.g. `SET_VOLUME`, `BLE_OPEN_LOCK`) |
| `status` | Status | `confirmed` / `catalogued` |
| `confirmed_frame` | bytes \| None | exact plaintext when confirmed (e.g. open seq 1) |
| `note` | str \| None | e.g. "direction byte 01 open / 00 close" |

The catalog is a collection of `OperationEntry` keyed by `(family.main_cmd, sub_cmd)`.
Sub-command bytes are only unique *within* a family, never globally.

## Control frame (builder output)

- Generic level-3 command: `main_cmd(1) + sub_cmd(1) + data(n)`.
- Confirmed operate frame (`SYSTEM 0x74`): `74 <dir:1> <seq:2 LE> <(base_dir+seq):2 LE>`
  — the feature-009 form, produced by `build_operate_frame`.

`build_control_frame(main_cmd, sub_cmd, data, seq)` returns the generic bytes and
documents that the trailer/sequence of non-`0x74` families is unverified.

## Initial confirmed set

| Family | sub | Name | Confirmed frame |
|--------|-----|------|-----------------|
| SYSTEM `01` | `74` | BLE_OPEN_LOCK (open) | `74010100b917` (seq 1, dir 01) |
| SYSTEM `01` | `74` | BLE_OPEN_LOCK (close) | `740001003912` (seq 1, dir 00) |
| SYSTEM `01` | `2f` | HEART_PCK (keepalive) | `2f012f` |
