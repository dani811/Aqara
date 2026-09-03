'use strict';
import Java from 'frida-java-bridge';

function report(m) { send('MSG:[DIAG] ' + m); }

var CANDIDATES = [
  'org.bouncycastle.crypto.modes.CCMBlockCipher',
];

Java.perform(function () {
  // Enumerate ALL loaded classes whose name mentions CCM / AESCCM / the lock crypto.
  report('scanning loaded classes for CCM / AESCCM / ahdoorlock crypto ...');
  var hits = [];
  try {
    Java.enumerateLoadedClassesSync().forEach(function (name) {
      if (/CCMBlockCipher|AESCCM|encryptAESCCM|ahdoorlock|ExpandedIv|AESCCMSecretKey/i.test(name)) {
        hits.push(name);
      }
    });
  } catch (e) { report('enumerate err: ' + e); }
  report('name-matched classes (' + hits.length + '): ' + JSON.stringify(hits.slice(0, 40)));

  CANDIDATES.concat(hits).slice(0, 12).forEach(function (cn) {
    try {
      var C = Java.use(cn);
      var decl = C.class.getDeclaredMethods();
      var names = [];
      for (var i = 0; i < decl.length; i++) {
        names.push(decl[i].getName() + '(' + decl[i].getParameterTypes().length + ')');
      }
      report('=== ' + cn + ' methods: ' + JSON.stringify(names));
      var fields = C.class.getDeclaredFields();
      var fn = [];
      for (var j = 0; j < fields.length; j++) fn.push(fields[j].getName());
      report('    fields: ' + JSON.stringify(fn));
    } catch (e) {
      report('use(' + cn + ') failed: ' + e);
    }
  });
  report('diag done');
});
