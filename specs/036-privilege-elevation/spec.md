# Feature Specification: U200 Privileged Session Elevation

**Feature Branch**: `feat/036-privilege-elevation`

**Created**: 2026-08-27

**Status**: Investigation (analysis-only; no live-lock steps until a trigger is found)

**Input**: Reverse-engineer why the Aqara U200 serves a whole tier of "sensitive"
control opcodes to the official app but not to our `aqara-ble` sessions, and find
the trigger that elevates a session so the library can read those settings over BLE.

## Background — what is proven (do not re-derive)

By decrypting the official app's own BLE session (keystream-reuse on the static
AES-CCM nonce; capture via `adb bugreport` btsnoop, no root/Frida — see
[settings-protocol.md](../../docs/devices/u200/settings-protocol.md)) we established:

- The read frame is `<opcode> <KIND> <body>`; KIND (family byte) matters.
- **Two tiers.** FREE opcodes answer any authenticated session: keepalive `0x2f`,
  MTU `0x4d`, firmware `0x0d`, lock status `0x07`, battery `0xde`, tongue `0x08`,
  door type `0xe0`, pull spring `0xe4`, work mode `0xee`, advanced `0xd8`, limits
  `0xe2`, verify-fail `0x94`, alarm-enable `0xcb`, timezone `0x33`.
- **PRIVILEGED (gated) tier — answered to the app, silent to us**: log sync `0x13`,
  `0x1f`, finger count `0x20`, language `0x68`, volume `0xc3`/`0x02`, alarm volume
  `0x84`, lock-setting `0x1a`, voice-OTA `0xa6`.
- Our auth message is byte-structurally IDENTICAL to the app's (`00 ft 10 01 00
  <len_le> <crc16(body)> …`, same account/phone_id). The privilege is NOT in the
  handshake format.

## Refuted elevation hypotheses (evidence in memory `app-reads-settings-bulk-blob`)

- **Keypad per read** — it is not per-read; the app read gated ops ~30 s after
  connect with no per-read touch.
- **Keypad held during read** — did not reproduce (held 50 s, still `(none)`).
- **Set-time `0x33`** — sent it, then read volume → `(none)`. Refuted live.
- **Log-sync `0x13` completes → elevates** — CIRCULAR and refuted: the lock does
  not answer OUR `0x13` at all (it is itself in the gated tier).
- **Session age / settling delay** (~10-30 s of keepalives) — refuted.
- **Response latency / queueing** — refuted (30 s listen after a volume read: 0
  frames).
- **Persistent session alone** (one auth, many frames via `read_burst`) — refuted.
- **BLE bonding/encryption** — refuted (the app's ATT is in the clear in the
  btsnoop, so its link is unbonded too).

The ONE positive datapoint (a single successful volume read from our ESP32) came
immediately after driving the APP to the volume screen — i.e. it likely rode a
transient lock-side elevated state the app had just established.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Identify the exact condition that elevates a session to the
  privileged tier, using ONLY offline analysis of already-captured data until a
  concrete, testable trigger exists (respect the user's time — no speculative
  live-lock probing).
- **FR-002**: The investigation MUST compare, field by field, the app's decrypted
  session vs. our library's session for anything the app does that we do not
  (cloud request parameters, BLE central address/identity, command order).
- **FR-003**: Any candidate trigger MUST be validated with a single, well-scoped
  live test that NEVER sends the actuation opcode (`0x74`) and is explained to the
  user before it runs.
- **FR-004**: If a trigger is found, expose the gated reads (volume/language/alarm
  volume) via the persistent-session `read_burst` path and add typed decoders +
  HA entities (continues spec 035).
- **FR-005**: The stable-link fix (supervision timeout / interval range, committed
  2026-08-27) is a prerequisite for any multi-frame live test and MUST stay.

### Candidate leads to analyze (ranked)

1. ~~**BLE central identity**~~ — **REFUTED 2026-08-27 by btsnoop analysis** (no
   live test needed). The phone connects with a **rotating RPA** (`LE Set Random
   Address 4a:a9:6b:54:eb:06`, own_addr_type=1; MSB `4a` bits `01` = resolvable
   private address), and the link is unbonded (no IRK). A rotating, unresolvable
   central address gives the lock NO stable identity to gate on → the privilege
   tier is NOT bound to the central address. Its public BD_ADDR (74:be:f3:16:77:f3)
   is not used for the connection.
2. **Cloud session material / cloud request (PRIME lead after 2026-08-27).** The
   app is privileged from the FIRST post-auth command: its first gated op (log sync
   0x13) is answered ~0.5 s after auth (clean session: auth done 11:19:50.97, RX
   0x13 at 11:19:51.826). Since every BLE-observable is IDENTICAL to ours (auth
   message format, 8-byte verifyData, RPA address, the cloud calls our library
   reimplements), the privilege must be granted CLOUD-SIDE and is invisible on the
   BLE link — either the session material (sessionKey/nonce/verifyData VALUES) is
   privilege-bearing, or the app's cloud request to mint it carries a
   role/scope/app-signature field our library's request omits. **To settle:**
   capture the app's HTTPS to the Aqara cloud (the `get_public_key` + `verify`
   calls) and diff request+response against `aqara_ble.kdf`. This needs an HTTPS
   MITM proxy and will fight the SecNeo app's likely cert pinning — a new, harder
   RE phase (its own spec when tackled).
3. ~~Command-stream diff~~ — effectively done: the app's extra commands (set-time
   0x33, log sync 0x13) were tested and do NOT elevate; 0x13 is itself gated. No
   single BLE command elevates.

### Leading conclusion (2026-08-27)

The privileged tier is **granted cloud-side at session mint time**, not by any BLE
command or the central address. Reproducing it likely requires diffing the app's
HTTPS cloud session-grant against our library's (lead 2) — OR accepting that the
Aqara cloud only mints a privileged session for the official (SecNeo-signed) app,
which we cannot forge without breaking that signing. The one transient success we
saw was our read riding the lock's short-lived elevated state left by the app.

## Success Criteria *(mandatory)*

- **SC-001**: The elevation trigger is identified and reproduced from our library
  (a gated opcode, e.g. volume `0xc3`, returns a real value), OR it is proven that
  the tier is bound to something we cannot replicate (e.g. a registered-central
  secret), with the evidence documented.
- **SC-002**: Zero actuation commands are sent during the investigation.
- **SC-003**: Each live test is pre-explained to the user and needs at most one
  scoped action from them.

## Out of Scope

- Actuation, user/credential management, temp/offline password.
- Any technique requiring root or defeating SecNeo (Frida) — ruled out and not
  needed.

## Assumptions

- The account/phone_id in `.env` are the registered owner's (recovered from the
  app), so account-level privilege should already match.
- The btsnoop captures already on disk (scratchpad) are sufficient for the offline
  diffs in FR-002/lead 2/lead 3.
