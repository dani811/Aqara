// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

"use strict";
// PURE READ-ONLY probe: list libhermes.so's exports. No Interceptor.attach,
// no Java.perform, no ART/JNI touch at all -- just Process.getModuleByName()
// + enumerateExports(), the same category of call as capture_ssl_native's
// Module.getExportByName() (already proven safe for hundreds of SSL calls).
// Goal: find the real call-dispatch/evaluate entry point in Hermes's own
// C++ surface, to hook NATIVELY later (never crossing into ART, so SecNeo's
// active-Java-hook crash -- confirmed twice tonight even on 17.2.12, see
// frida-repack-strategy memory -- should not apply).
setInterval(function () {}, 5000);

function L(s) { console.log("HERMES ts=" + Date.now() + " " + s); }

try {
  var mod = Process.getModuleByName("libhermes.so");
  L("FOUND libhermes.so base=" + mod.base + " size=" + mod.size + " path=" + mod.path);
  var exports = mod.enumerateExports();
  L("EXPORT_COUNT " + exports.length);
  // Print every export whose name looks relevant: evaluate/call/dispatch/
  // interpret/function invocation surface.
  var interesting = exports.filter(function (e) {
    var n = e.name.toLowerCase();
    return n.indexOf("evaluate") !== -1 ||
           n.indexOf("call") !== -1 ||
           n.indexOf("invoke") !== -1 ||
           n.indexOf("dispatch") !== -1 ||
           n.indexOf("interpret") !== -1 ||
           n.indexOf("runtime") !== -1 ||
           n.indexOf("execute") !== -1;
  });
  L("INTERESTING_COUNT " + interesting.length);
  interesting.forEach(function (e) {
    L("EXPORT " + e.type + " " + e.name + " @ " + e.address);
  });
} catch (e) {
  L("ERROR " + e + "\n" + e.stack);
}
