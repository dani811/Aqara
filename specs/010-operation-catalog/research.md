# Phase 0 Research: Lock operation & settings catalog

No open `NEEDS CLARIFICATION`. This phase records the decisions behind the catalog.

## Decision: the catalog is a faithful copy of the decompiled enum, honestly labelled

- **Decision**: Reproduce the family/sub-command map from the app's decompiled
  `BleCommandConstant.ts` (as captured in the RE project's `operaciones-u200.md`),
  one entry per operation, each with a `confirmed` / `catalogued` status.
- **Rationale**: The enum is the authoritative list of what the lock accepts. The
  status field is the guard against the `1f031f`/`200320` failure mode — a
  decompiled name is not proof of the wire bytes until captured.
- **Evidence**: `confirmed` today = the feature-009 live captures (open `0x74`
  dir 01, close `0x74` dir 00, keepalive `0x2f`). Everything else is `catalogued`.

## Decision: generic frame builder generalises `build_operate_frame`

- **Decision**: Add `build_control_frame(main_cmd, sub_cmd, data=b"", seq=1)`
  producing the level-3 plaintext. The confirmed `0x74` operate frame keeps its
  additive-trailer form via the existing `build_operate_frame`; the generic
  builder emits `mainCmd subCmd data` and is explicit that the trailer/sequence
  behaviour of non-`0x74` families is **not** yet verified.
- **Rationale**: One builder lets integrators construct any command; keeping the
  confirmed operate frame separate avoids implying an unverified structure for
  other families.
- **Alternatives considered**: assume every family uses the `0x74` trailer —
  rejected: no evidence; only `0x74` was captured. Emit only `mainCmd subCmd data`
  with no trailer for generic commands, and document the uncertainty.

## Command families (first frame byte)

`01` SYSTEM · `02` USER · `03` LOG · `04` ALARM · `05` DEVICELOG · `06` XXQ ·
`07` SYSTEM_EXT · `3f` LONG. Reply byte = `mainCmd | 0x80`.

## Promotion path for a catalogued entry

Two documented routes to recover a command's exact `data`, both from the RE
project: (1) read the app builder in the bundle (`sendAddPasswordCmd`,
`autoLockTimeCmd`, …); (2) capture live — reinstall the Frida-gadget app, hook
`AqEdUtils.encryptAESCCM`, perform the operation once, read the plaintext
`mainCmd subCmd data`. Route (2) is exactly how feature 009 confirmed open/close.
