/*
 * probe_ota_0x90.js — locate where the app mints the 17-byte 0x90 OTA commit
 * token that gates the language voice-pack transfer to ff91.
 *
 * WHY: we reproduced every layer of the language OTA except the value of the
 * `90 0d …` (17-byte) token written to ff91 at transfer start/end. It is built
 * in a NATIVE module (not the decompiled JS — see docs/reference/rn-device-
 * plugins.md), and is per-app-process. This probe watches the native crypto
 * core to catch that value being produced and, via a backtrace, locate the
 * function that builds it — so we can learn its derivation (session key? cloud?
 * counter?) and compute it ourselves inside aqara_ble's authenticated session.
 *
 * SAFE UNDER SecNeo: native Interceptor.attach on .so exports only — never a
 * Java method override (see docs/reference/native-libs.md "Golden rule").
 *
 * RUN (gadget-repacked app cold-started + `adb forward tcp:27042 tcp:27042`):
 *     python3 tools/frida_attach.py tools/probe_ota_0x90.js --seconds 300
 * THEN, while attached: in the app, trigger a Français voice download (the full
 * OTA). Watch stdout for lines tagged 0x90 / 17B / OTA.
 *
 * Frida 17 GumJS API: Module.getExportByName / Process.getModuleByName
 * (Module.findExportByName was removed).
 */
'use strict';

// The known captured token value — if it recurs, we've found a persisted/
// derived source. (It is per-process, so a fresh process yields a NEW value;
// this is here to recognise a match if the same process is re-observed.)
var KNOWN_90 = '55d9bea3755376155b749ca0066d93';

function hex(ptr, len) {
  try { return Memory.readByteArray(ptr, len); } catch (e) { return null; }
}
function toHexStr(ptr, len) {
  var a = new Uint8Array(hex(ptr, len));
  var s = '';
  for (var i = 0; i < a.length; i++) s += ('0' + a[i].toString(16)).slice(-2);
  return s;
}
function looksLikeToken(bytes) {
  // 17-byte frame led by 0x90, or the 15-byte payload, or the known value.
  if (!bytes) return false;
  var a = new Uint8Array(bytes);
  if (a.length >= 1 && a[0] === 0x90) return true;
  var s = '';
  for (var i = 0; i < a.length; i++) s += ('0' + a[i].toString(16)).slice(-2);
  return s.indexOf(KNOWN_90) !== -1;
}

function report(tag, msg) { send('MSG:[' + tag + '] ' + msg); }

// 1) dlopen trace — catch a BLE-crypto lib (e.g. libaqara_ed.so) loading when
//    BLE connects; native-libs.md flags this as a lead worth enumerating.
['android_dlopen_ext', 'dlopen'].forEach(function (name) {
  var p = null;
  try { p = Module.getExportByName(null, name); } catch (e) {}
  if (!p) return;
  Interceptor.attach(p, {
    onEnter: function (args) { try { this.path = args[0].readCString(); } catch (e) {} },
    onLeave: function () {
      if (this.path && /aqara_ed|ble|lumidev|crypto/i.test(this.path)) {
        report('dlopen', this.path);
      }
    },
  });
});

// 2) Hook liblumidevsdk.so's native crypto internals. Signatures are unknown
//    (docs/reference/native-libs.md C-stage-2), so we log arg pointers and any
//    small output buffer, flagging 17-byte / 0x90-leading data + a backtrace.
// (lib, [exported function names]) to hook. libaqara_ed is the small
// encrypt/decrypt lib; liblumidevsdk is the crypto core. We scan both.
var LIB_TARGETS = {
  'liblumidevsdk.so': ['aesEncryptedContent', 'aesDecryptedContent',
                       'getEncryptedData', 'getDecryptedData'],
  'libaqara_ed.so': ['ed_encode', 'ed_encode_x64', 'cipher_encode',
                     'ed_decode', 'cipher_decode'],
};
var hooked = {};  // lib -> true once its functions are attached

function scanArgsForToken(sym, args, ctx) {
  for (var i = 0; i < 6; i++) {
    var b = hex(args[i], 17);
    if (looksLikeToken(b)) {
      report('0x90', sym + ' arg#' + i + ' -> ' + toHexStr(args[i], 17));
      try {
        report('bt', Thread.backtrace(ctx, Backtracer.ACCURATE)
          .map(DebugSymbol.fromAddress).join('\n    '));
      } catch (e) {}
      return true;
    }
  }
  return false;
}

var NAME_RE = /encrypt|decrypt|encode|decode|cipher|aes|sign|token|ota|getEncrypted|getDecrypted/i;

function hookLib(lib) {
  if (hooked[lib]) return true;
  var mod;
  try { mod = Process.getModuleByName(lib); } catch (e) { return false; }
  report('module', lib + ' present @ ' + mod.base);
  // Enumerate REAL exports + local symbols (Frida's view differs from radare2;
  // some symbols are not in the dynamic export table). Hook any crypto-ish one.
  var syms = [];
  try { mod.enumerateExports().forEach(function (e) { if (e.type === 'function') syms.push(e); }); } catch (e) {}
  try { mod.enumerateSymbols().forEach(function (s) { if (s.type === 'function' && s.address && !s.address.isNull()) syms.push(s); }); } catch (e) {}
  var seen = {};
  var n = 0;
  syms.forEach(function (s) {
    if (!s.name || !NAME_RE.test(s.name)) return;
    var key = s.address.toString();
    if (seen[key]) return; seen[key] = 1;
    var addr = s.address;
    var symName = lib + '!' + s.name;
    Interceptor.attach(addr, {
      onEnter: function (args) {
        this.sym = symName;
        this.args = [args[0], args[1], args[2], args[3], args[4], args[5]];
        scanArgsForToken(this.sym + '(enter)', this.args, this.context);
      },
      onLeave: function (retval) {
        scanArgsForToken(this.sym + '(leave)', this.args, this.context);
        if (looksLikeToken(hex(retval, 17))) {
          report('0x90', this.sym + ' RET -> ' + toHexStr(retval, 17));
          try { report('bt', Thread.backtrace(this.context, Backtracer.ACCURATE)
            .map(DebugSymbol.fromAddress).join('\n    ')); } catch (e) {}
        }
      },
    });
    n++;
  });
  report('hook', lib + ' hooked ' + n + ' crypto-ish functions');
  hooked[lib] = true;
  return true;
}

// Retry indefinitely (every 2s) until each target lib is present + hooked —
// the crypto libs load lazily (on first cloud/BLE use), which can be well after
// process start.
function hookAll() {
  var allDone = true;
  Object.keys(LIB_TARGETS).forEach(function (lib) { if (!hookLib(lib)) allDone = false; });
  return allDone;
}
if (!hookAll()) {
  var iv = setInterval(function () { if (hookAll()) clearInterval(iv); }, 2000);
}

report('ready', 'probe_ota_0x90 loaded; trigger a Français voice download now');
