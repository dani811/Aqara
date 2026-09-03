// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

// Probe liblumidevsdk.so's getSignHead (the cloud Sign function that
// aqara_ble.cloud_crypto.compute_sign reimplements). NATIVE Interceptor.attach
// on the export address — never touches the ART bridge (safe under SecNeo).
//
// getSignHead is a JNI export: Java_..._getSignHead(JNIEnv* env, jclass, ...).
// We don't yet know its Java arg shape, so this PROBE logs, on each call:
//   - the raw arg registers x2..x7 (the Java args after env+class)
//   - each interpreted as a JNI String (via env->GetStringUTFChars)
//   - the return value interpreted as a JNI String (the computed Sign, or the
//     whole signed header — GetStringUTFChars on retval in onLeave)
// From that we learn whether the app passes the preimage as one jstring, or
// the components separately, and what the output is. Then the real capture
// hook can read exactly the right things.
//
// Attach: python3 tools/frida_attach.py tools/probe_getsignhead.js --seconds 120
// Then generate a cloud request in the app (pull-to-refresh, open a screen).
'use strict';

function L(s) { send('SIGNHEAD ' + s); }

setTimeout(function () {
  var addr;
  try {
    addr = Process.getModuleByName('liblumidevsdk.so').findExportByName('Java_com_lumi_lumidevsdk_LumiDevSDK_getSignHead');
  } catch (e) { L('ERR module/export: ' + e); return; }
  if (!addr) { L('ERR getSignHead not found'); return; }
  L('hooking getSignHead @ ' + addr);

  // Helper: env->GetStringUTFChars(env, jstr, NULL). JNIEnv* is a pointer to a
  // function table; GetStringUTFChars is at index 169 on ARM64 (standard JNI
  // layout). Returns a char*.
  function jstrToStr(env, jstr) {
    if (jstr.isNull()) return '<null>';
    try {
      var fnTab = env.readPointer();
      var getUtf = fnTab.add(169 * Process.pointerSize).readPointer();
      var f = new NativeFunction(getUtf, 'pointer', ['pointer', 'pointer', 'pointer']);
      var cstr = f(env, jstr, ptr(0));
      if (cstr.isNull()) return '<utf-null>';
      var s = cstr.readUtf8String();
      return s;
    } catch (e) { return '<jstr-err:' + e + '>'; }
  }

  Interceptor.attach(addr, {
    onEnter: function (args) {
      this.env = args[0];
      L('---- CALL ----');
      for (var i = 2; i <= 7; i++) {
        var a = args[i];
        var asStr = jstrToStr(this.env, a);
        L('arg' + i + ' ptr=' + a + '  asJString=' + JSON.stringify(asStr));
      }
    },
    onLeave: function (retval) {
      var asStr = jstrToStr(this.env, retval);
      L('RET ptr=' + retval + '  asJString=' + JSON.stringify(asStr));
    }
  });
  L('installed');
}, 0);
