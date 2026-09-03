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
