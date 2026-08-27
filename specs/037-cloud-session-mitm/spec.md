# Feature Specification: Cloud session-grant MITM (privilege capture)

**Feature Branch**: `feat/037-cloud-session-mitm`

**Created**: 2026-08-27

**Status**: Planned (blocked-hard research; open only when ready to invest)

**Input**: Capture the official Aqara app's HTTPS traffic to the Aqara cloud during
a lock session, and diff the session-grant (`get_public_key` + `verify`) request +
response against our `aqara_ble.kdf`, to find why the cloud mints a **privileged**
session for the app but not for our library (see `specs/036-privilege-elevation`).

## Background (why this phase exists)

Spec 036 proved the U200's sensitive-settings tier (volume/language/finger/log/…)
is granted **cloud-side at session mint time** and is invisible on the BLE link:
the app is privileged from its first post-auth command, and every BLE-observable
(auth format, 8-byte verifyData, RPA address, unbonded link) is identical to ours.
So the only place the privilege can differ is the **cloud HTTP session-grant**. Our
`kdf` reimplementation authenticates fine (free reads work) but evidently obtains
non-privileged session material.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Intercept the app↔Aqara-cloud HTTPS for one full lock session (login,
  `get_public_key`, `verify`/session-material). A phone-level MITM proxy
  (mitmproxy/Charles) with a trusted CA.
- **FR-002**: Defeat/áwork around the app's certificate pinning. The app is
  **SecNeo-hardened** (libDexHelper) so standard user-CA trust likely fails; options
  (in rising effort): system-CA on a rooted/emulated device (blocked — no root),
  `mitmproxy` + Android network-security-config on a debuggable rebuild (blocked —
  SecNeo), Frida SSL-unpinning (blocked — SecNeo anti-Frida), or a hardware/network
  MITM with a pinning-bypass. This is the crux risk and may prove infeasible.
- **FR-003**: Diff the captured requests + responses field-by-field against what
  `aqara_ble/kdf.py` sends/receives (headers, body params, signed fields, and any
  role/scope/device-capability field in the response).
- **FR-004**: If a privilege-bearing field is found, replicate it in `kdf` and
  verify a gated read (volume `0xc3`) returns a real value from our session.
- **FR-005**: No lock actuation (`0x74`) at any point; capture is passive.

## Attempt log — 2026-08-27 (walls confirmed empirically)

First MITM attempt with mitmproxy 12.2.0 (own device/account):

- **Regular HTTP proxy (WiFi `http_proxy` = Mac:8080):** works for cooperating
  apps — the phone's browser/Google/Spotify all appeared in the proxy log (with
  TLS failures until a CA was trusted). But the **Aqara app made ZERO connections
  through it** — it **ignores the system HTTP proxy** (hardened-app behaviour;
  Context7 confirms this is the known case that needs WireGuard/transparent/local
  modes).
- **User-CA install:** Android 14 refuses CA install via file intent ("install CA
  in Settings"); installed via Settings → Encryption & credentials as a **user CA**.
  Modern/hardened apps distrust user CAs, so this alone would not decrypt the app.
- **WireGuard mode** (`mitmdump --mode wireguard`, tun0 up on the phone): routing
  came up but traffic failed end-to-end ("error de red" on the phone, empty proxy
  log — a mitmproxy-WG DNS/forwarding issue that needs more setup), and the
  user-CA/pinning wall still sits behind it.

**Conclusion:** standard MITM of this SecNeo app **without root** hits compounding
walls (proxy bypass → WireGuard plumbing → user-CA distrust → likely pinning). This
confirms the crux risk. To proceed would need root (system-CA + iptables transparent
redirect) or app instrumentation (Frida SSL-unpin) — both blocked (unrooted phone +
SecNeo). Cleanup after the attempt: revert phone `http_proxy`, re-enable mobile
data, remove the installed mitmproxy user CA, delete the WireGuard tunnel.

## Success Criteria

- **SC-001**: Either the cloud field/step that grants privilege is identified and
  replicated (a gated read succeeds from our library), OR it is proven that the
  grant is bound to a secret only the SecNeo-signed app holds (documented, closes
  the line honestly).

## Out of Scope / risks

- Rooting the phone or repacking the SecNeo APK (both ruled out in 036).
- If pinning cannot be bypassed without app instrumentation, this phase is a dead
  end and the gated tier stays app-only — accept and document.

## Assumptions

- The free-tier BLE functionality (event feed, lock/unlock, non-gated reads) is
  already shipped and unaffected; this phase only concerns the sensitive settings.

---

## Related future goal (not this spec): replicate device pairing/union

The user wants, as a future objective, to **replicate the device pairing/union flow**
(adding a U200 to the account from scratch — the provisioning handshake, not just
operating an already-bound lock). That is a separate large feature (its own spec
when tackled); the cloud MITM tooling built here (HTTPS capture of the app's cloud
calls) would directly serve it, since pairing is cloud-heavy. Tracked as a note so
it is not lost.
