# frida-17.17.0 — CONFIRMED BROKEN, don't rebuild without a reason

**The gadget never connects to a matched 17.17.0 host** — the handshake
dies with "connection closed" before Frida can even report the gadget's
version (same symptom class as a version *mismatch*, but this was with a
matched pair — see `../README.md`'s status table and `../../frida-setup.md`
for the exact quote). This is a recorded negative result from before the
project settled on 16.7.19, not a guess and not the same failure as the
SecNeo Java-hook crash (this one never gets far enough to test that).

If you have a specific reason to believe this has since changed (a newer
patch, a different `-t`/loader-class target, a different device), rebuild
with `tools/repack_apk.sh 17.17.0` and update this file with the real
outcome either way — don't let a repeat negative silently vanish again.
