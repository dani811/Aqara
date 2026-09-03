// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

"use strict";
setInterval(function () {}, 5000);
function L(s) { console.log("MODLIST ts=" + Date.now() + " " + s); }
try {
  var mods = Process.enumerateModules();
  L("MODULE_COUNT " + mods.length);
  mods.forEach(function (m) {
    if (m.name.toLowerCase().indexOf("hermes") !== -1 ||
        m.name.toLowerCase().indexOf("react") !== -1 ||
        m.name.toLowerCase().indexOf("jsi") !== -1) {
      L("MOD " + m.name + " base=" + m.base + " size=" + m.size + " path=" + m.path);
    }
  });
  L("DONE");
} catch (e) {
  L("ERROR " + e);
}
