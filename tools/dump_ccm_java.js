// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

'use strict';
// Frida 17: Java bridge via frida-compile. Build:
//   .venv/bin/frida-compile tools/dump_ccm_java.js -o tools/dump_ccm_java.agent.js
// Persistent: ONE attach, re-scans loaded classes every 2.5s so crypto classes
// that only load once you enter the lock session get hooked without re-attaching.
import Java from 'frida-java-bridge';

function hex(jb){ if(jb===null) return 'null'; var s=''; for(var i=0;i<jb.length;i++){var b=jb[i]&0xff; s+=('0'+b.toString(16)).slice(-2);} return s; }
function report(t,m){ send('MSG:['+t+'] '+m); }

Java.perform(function(){
  report('ready','dump_ccm_java PERSISTENT loaded — will re-scan every 2.5s');
  var hooked = {};        // class.method already hooked
  var seenClasses = {};   // classes already enumerated-and-processed

  function scan(){
    var targets = [];
    try {
      Java.enumerateLoadedClassesSync().forEach(function(n){
        if (/AqEd|encryptAESCCM|AESCCM|CCMBlockCipher|ahdoorlock|BleCrypt|ExpandedIv|LumiCrypt|Encryption/i.test(n)) targets.push(n);
      });
    } catch(e){ return; }
    targets.forEach(function(cn){
      if (seenClasses[cn]) return;
      seenClasses[cn] = true;
      try {
        var C = Java.use(cn);
        var methods = C.class.getDeclaredMethods();
        for (var i=0;i<methods.length;i++){
          var m = methods[i]; var mn = m.getName();
          var pt = m.getParameterTypes(); var rt = m.getReturnType().getName();
          var hasBytes = false; for (var j=0;j<pt.length;j++){ if(pt[j].getName()==='[B') hasBytes=true; }
          if (!hasBytes || rt !== '[B') continue;
          var key = cn+'.'+mn;
          if (hooked[key]) continue;
          try {
            C[mn].overloads.forEach(function(ov){
              ov.implementation = function(){
                var a = arguments;
                var ins=[]; for (var k=0;k<a.length;k++){ if(a[k]&&a[k].length!==undefined && a[k].$className===undefined){ try{ins.push(hex(a[k]));}catch(e){ins.push('?');} } }
                var ret = ov.apply(this, a);
                report('CRYPTO', cn+'.'+mn+'  IN='+JSON.stringify(ins)+'  OUT='+(ret?hex(ret):'null'));
                return ret;
              };
            });
            hooked[key] = true;
            report('hooked', key);
          } catch(e){}
        }
      } catch(e){}
    });
    var n = Object.keys(hooked).length;
    if (n) report('scan', 'hooked methods so far: '+n);
  }

  scan();
  // setInterval callbacks run on Frida's JS thread, NOT attached to the JVM, so
  // Java.* calls there throw. Re-attach the current thread each tick via Java.perform.
  setInterval(function(){ Java.perform(scan); }, 2500);
});
