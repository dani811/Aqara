#!/usr/bin/env bash
# Repack the official Aqara Home APK with a frida-gadget of a given version,
# working around objection's known lib-path packaging bug, and place the
# result under tools/repacked-apks/frida-<version>/.
#
# Consolidates what used to be scattered, one-off shell commands across
# tools/frida-setup.md and past session transcripts into a single,
# parameterized, repeatable script — see tools/repacked-apks/README.md for
# why this exists and the per-version status table.
#
# Usage:
#   tools/repack_apk.sh <frida-version> [path-to-original-apk]
#
# Example:
#   tools/repack_apk.sh 17.2.12
#   tools/repack_apk.sh 17.2.12 tools/repacked-apks/original/aqara-official.apk
#
# Requires: objection (pip), aapt/aapt2/zipalign/apksigner (Android SDK
# build-tools, auto-discovered under ~/Library/Android/sdk if not on PATH).
#
# THE INVARIANT (see tools/frida-setup.md): the host `frida`/`frida-tools`
# version used to ATTACH to this gadget MUST equal <frida-version> exactly.
# This script does not touch the host install — bump
# tools/requirements-frida.txt yourself when you switch which version you're
# driving day to day.

set -euo pipefail

VERSION="${1:?Usage: repack_apk.sh <frida-version> [path-to-original-apk]}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/tools/repacked-apks/frida-$VERSION"
ORIGINAL_APK="${2:-$REPO_ROOT/tools/repacked-apks/original/aqara-official.apk}"
# Resolve to an absolute path up front — the script cd's into a work dir
# below, and objection's own APK-source check runs from there.
case "$ORIGINAL_APK" in
  /*) ;;
  *) ORIGINAL_APK="$(cd "$(dirname "$ORIGINAL_APK")" && pwd)/$(basename "$ORIGINAL_APK")" ;;
esac

if [[ ! -f "$ORIGINAL_APK" ]]; then
  echo "error: original APK not found at $ORIGINAL_APK" >&2
  echo "  Pull it from the phone first, e.g.:" >&2
  echo "    adb shell pm path com.lumiunited.aqarahome.play" >&2
  echo "    adb pull <path-from-above> $ORIGINAL_APK" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
echo "== Repacking Aqara Home with frida-gadget $VERSION =="
echo "   source:  $ORIGINAL_APK"
echo "   out dir: $OUT_DIR"

# objection's own patchapk shells out to aapt (for the manifest edit) before
# this script's own build-tools lookup would otherwise run — put build-tools
# on PATH up front so both objection AND our own zipalign/apksigner find it.
if ! command -v aapt >/dev/null 2>&1; then
  BT=$(find "$HOME/Library/Android/sdk/build-tools" -maxdepth 1 -type d 2>/dev/null | sort -V | tail -1)
  [[ -n "$BT" ]] && export PATH="$BT:$PATH"
fi

WORK="$OUT_DIR/.work"
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

# 1. objection's patchapk downloads the gadget itself and injects the loader
#    into SecNeo's own wrapper class (the real launch activity's dex is
#    encrypted, so apktool/objection can't patch it directly).
objection patchapk \
  -s "$ORIGINAL_APK" \
  -a arm64 \
  -V "$VERSION" \
  -t com.secneo.apkwrapper.AW

# objection writes its output NEXT TO THE SOURCE APK (i.e. in
# $ORIGINAL_APK's directory), not into $PWD/$WORK — move it here so the
# rest of this script can treat it uniformly.
SRC_DIR="$(dirname "$ORIGINAL_APK")"
RAW_OUTPUT=$(ls "$SRC_DIR"/*.objection.apk 2>/dev/null | head -1)
if [[ -z "$RAW_OUTPUT" ]]; then
  echo "error: objection did not produce a *.objection.apk next to $ORIGINAL_APK — check its output above" >&2
  exit 1
fi
PATCHED_APK="$(basename "$RAW_OUTPUT")"
mv "$RAW_OUTPUT" "./$PATCHED_APK"

# 2. Known objection packaging bug: the gadget .so lands at lib/arm64/
#    instead of lib/arm64-v8a/. Android's PackageManager silently ignores
#    the misplaced lib, so the gadget never loads unless this is fixed.
echo "== Fixing lib/arm64 -> lib/arm64-v8a packaging bug =="
UNPACK_DIR="unpacked"
mkdir -p "$UNPACK_DIR"
(cd "$UNPACK_DIR" && unzip -q -o "../$PATCHED_APK")

if [[ -d "$UNPACK_DIR/lib/arm64" && ! -d "$UNPACK_DIR/lib/arm64-v8a" ]]; then
  mv "$UNPACK_DIR/lib/arm64" "$UNPACK_DIR/lib/arm64-v8a"
elif [[ -d "$UNPACK_DIR/lib/arm64" ]]; then
  cp -n "$UNPACK_DIR/lib/arm64/"* "$UNPACK_DIR/lib/arm64-v8a/" 2>/dev/null || true
  rm -rf "$UNPACK_DIR/lib/arm64"
fi

FIXED_APK="$OUT_DIR/aqara-repacked.apk"
# resources.arsc MUST stay stored (uncompressed) — Android R+ rejects an
# APK where it's compressed. objection's own output has it stored
# correctly; a naive `zip -r` over the whole tree recompresses it and
# breaks install with "Failed parse ... requires resources.arsc ... to be
# stored uncompressed". Zip everything else normally, add this one file
# separately with -0.
(cd "$UNPACK_DIR" && zip -q -r -X "../fixed.apk" . -x "resources.arsc")
(cd "$UNPACK_DIR" && zip -q -X -0 "../fixed.apk" resources.arsc)

# 3. Locate Android build-tools (aapt2/zipalign/apksigner) if not on PATH.
BUILD_TOOLS=""
if command -v zipalign >/dev/null 2>&1; then
  BUILD_TOOLS=""
else
  BUILD_TOOLS=$(find "$HOME/Library/Android/sdk/build-tools" -maxdepth 1 -type d 2>/dev/null | sort -V | tail -1)
  [[ -z "$BUILD_TOOLS" ]] && { echo "error: no Android build-tools found; install via sdkmanager or add to PATH" >&2; exit 1; }
  export PATH="$BUILD_TOOLS:$PATH"
fi

# 4. zipalign, then re-sign with objection's own debug keystore (same one
#    it always uses — this is a local debug key, not a secret).
zipalign -f -p 4 fixed.apk aligned.apk
OBJECTION_JKS=$(python3 -c "import objection, os; print(os.path.join(os.path.dirname(objection.__file__), 'utils', 'assets', 'objection.jks'))")
apksigner sign \
  --ks "$OBJECTION_JKS" \
  --ks-key-alias objection \
  --ks-pass pass:basil-joule-bug \
  --out "$FIXED_APK" \
  aligned.apk

echo "== Done: $FIXED_APK =="
echo "Install with: adb install -r '$FIXED_APK'"
echo "Then verify with: python3 tools/check_gadget.py"

cd "$REPO_ROOT"
cat > "$OUT_DIR/BUILD_INFO.txt" <<EOF
Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Frida gadget version: $VERSION
Source APK: $ORIGINAL_APK
EOF
rm -rf "$WORK"
