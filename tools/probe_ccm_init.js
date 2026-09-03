/*
 * probe_ccm_init.js — capture the real AES-CCM parameters (key / nonce / AAD /
 * plaintext / ciphertext) of every CCM op, to crack the language-OTA `0x90`.
 *
 * The short-pack is  mainCmd ‖ AES-CCM(sessionKey, expandedIv, nonce,
 * pt=subCmd‖data‖CRC16, aad=mainCmd‖subCmd‖data)  (getMiotShortPackString,
 * decompiled.js @242855). `encryptAESCCM` is Java over BouncyCastle, in the
 * SecNeo-packed DEX blob `libdatajar.so`. See
 * docs/devices/u200/ota-0x90-investigation.md §9.
 *
 * BouncyCastle here is OBFUSCATED (methods a(),b(),c()… — only reset() keeps its
 * name), so we resolve init/processPacket by PARAMETER TYPES, and dump the
 * CipherParameters object by reflecting over its fields (getters are obfuscated
 * too). The only unknown is `expandedIv` (Java-derived, not in the cloud verify
 * nor the JS) — read it live off the CCM engine alongside OUR derivable
 * sessionKey+nonce to learn if expandedIv=f(sessionKey,nonce) [→ offline] or
 * f(hidden ECDH) [→ hook each run]. Also yields the exact `0x90` plaintext.
 *
 * Build:  .venv/bin/frida-compile tools/probe_ccm_init.js -o tools/probe_ccm_init.agent.js
 * Load :  python tools/frida_attach.py tools/probe_ccm_init.agent.js --seconds 300
 * THEN, in the app: trigger a voice-pack (language OTA) download.
 */
'use strict';
import Java from 'frida-java-bridge';

var CCM_CLASS = 'org.bouncycastle.crypto.modes.CCMBlockCipher';

function report(msg) { send('MSG:[CCM] ' + msg); }

function jbytesToHex(jarr) {
  if (jarr === null || jarr === undefined) return '(null)';
  try { jarr = Java.array('byte', jarr); } catch (e) {}
  try {
    var n = jarr.length;
    if (n === undefined) return '(len undefined; type ' + (typeof jarr) + ')';
    var out = '';
    for (var i = 0; i < n; i++) {
      var b = jarr[i] & 0xff;
      out += ('0' + b.toString(16)).slice(-2);
    }
    return out + ' (' + n + 'B)';
  } catch (e) { return '(unreadable:' + e + ')'; }
}

function jbytesRangeHex(jarr, off, len) {
  if (jarr === null || jarr === undefined) return '(null)';
  try {
    var out = '';
    for (var i = off; i < off + len; i++) {
      var b = jarr[i] & 0xff;
      out += ('0' + b.toString(16)).slice(-2);
    }
    return out;
  } catch (e) { return '(unreadable:' + e + ')'; }
}

// Reflectively dump every field of a Java object (one level deep for nested
// objects like KeyParameter). Prints byte[] as hex, primitives as-is — this
// sidesteps the obfuscated getter names on AEADParameters/KeyParameter.
function dumpFields(obj, indent, depth) {
  if (obj === null || obj === undefined) { report(indent + '(null)'); return; }
  try { obj = Java.cast(obj, Java.use('java.lang.Object')); } catch (e) {}
  var cls;
  try { cls = obj.getClass(); } catch (e) { report(indent + '(no class: ' + e + ')'); return; }
  var cname;
  try { cname = cls.getName(); } catch (e) { cname = '?'; }
  report(indent + 'class ' + cname);
  var fields;
  try { fields = cls.getDeclaredFields(); } catch (e) { report(indent + '  (fields err: ' + e + ')'); return; }
  for (var i = 0; i < fields.length; i++) {
    var f = fields[i];
    var fname, ftype, val;
    try { fname = f.getName(); } catch (e) { fname = '?'; }
    try { ftype = f.getType().getName(); } catch (e) { ftype = '?'; }
    try { f.setAccessible(true); val = f.get(obj); } catch (e) { report(indent + '  ' + fname + ' (' + ftype + ') = <no access: ' + e + '>'); continue; }
    if (ftype === '[B') {
      report(indent + '  ' + fname + ' ([B) = ' + jbytesToHex(val));
    } else if (ftype === 'int' || ftype === 'long' || ftype === 'boolean' || ftype === 'short' || ftype === 'byte') {
      report(indent + '  ' + fname + ' (' + ftype + ') = ' + val);
    } else if (val !== null && depth > 0 && /KeyParameter|Parameters|ParametersWith/i.test(ftype)) {
      report(indent + '  ' + fname + ' (' + ftype + ') ->');
      dumpFields(val, indent + '    ', depth - 1);
    } else {
      report(indent + '  ' + fname + ' (' + ftype + ') = ' + (val === null ? 'null' : '<obj>'));
    }
  }
}

function bindClassLoaderFor(className) {
  try { Java.use(className); return true; } catch (e) {}
  var found = false;
  Java.enumerateClassLoadersSync().forEach(function (loader) {
    if (found) return;
    try {
      if (loader.findClass) loader.findClass(className);
      Java.classFactory.loader = loader;
      Java.use(className);
      found = true;
    } catch (e2) {}
  });
  return found;
}

function shortBacktrace() {
  try {
    var Exception = Java.use('java.lang.Exception');
    var Log = Java.use('android.util.Log');
    var st = '' + Log.getStackTraceString(Exception.$new());
    var lines = st.split('\n');
    var keep = [];
    for (var i = 0; i < lines.length && keep.length < 10; i++) {
      if (/lumi|aqara|ymodem|ota|ahdoorlock|[Ee]ncrypt/.test(lines[i])) keep.push(lines[i].trim());
    }
    return keep.length ? keep.join(' | ') : '(no app frames)';
  } catch (e) { return '(bt failed: ' + e + ')'; }
}

Java.perform(function () {
  if (!bindClassLoaderFor(CCM_CLASS)) {
    report('FATAL: cannot resolve ' + CCM_CLASS + ' — connect the lock in the app first, then re-run.');
    return;
  }
  var CCM = Java.use(CCM_CLASS);
  var methods = CCM.class.getDeclaredMethods();

  var initName = null, ppName = null, pbName = null, dfName = null;
  for (var i = 0; i < methods.length; i++) {
    var m = methods[i];
    var pn = m.getName();
    var pts = m.getParameterTypes();
    var rt = m.getReturnType().getName();
    var sig = [];
    for (var j = 0; j < pts.length; j++) sig.push(pts[j].getName());

    if (pts.length === 2 && sig[0] === 'boolean' && !initName) {
      initName = pn;
      report('resolved init -> ' + pn + '(' + sig.join(', ') + ')');
    }
    if (pts.length === 3 && sig[0] === '[B' && sig[1] === 'int' && sig[2] === 'int' && rt === '[B' && !ppName) {
      ppName = pn;
      report('resolved processPacket -> ' + pn + '(' + sig.join(', ') + ') : ' + rt);
    }
    // processBytes(byte[] in, int inOff, int len, byte[] out, int outOff): int
    if (pts.length === 5 && sig[0] === '[B' && sig[1] === 'int' && sig[2] === 'int' && sig[3] === '[B' && sig[4] === 'int' && !pbName) {
      pbName = pn;
      report('resolved processBytes -> ' + pn + '(' + sig.join(', ') + ')');
    }
    // doFinal(byte[] out, int outOff): int
    if (pts.length === 2 && sig[0] === '[B' && sig[1] === 'int' && rt === 'int' && !dfName) {
      dfName = pn;
      report('resolved doFinal -> ' + pn + '(' + sig.join(', ') + ')');
    }
  }

  // Accumulate processBytes input at module scope (CCM ops here are sequential),
  // flush on doFinal.
  var PENDING_IN = '';
  if (pbName) {
    try {
      CCM[pbName].overload('[B', 'int', 'int', '[B', 'int').implementation = function (inb, io, il, ob, oo) {
        try { PENDING_IN += jbytesRangeHex(inb, io, il); } catch (e) {}
        return this[pbName](inb, io, il, ob, oo);
      };
      report('hooked ' + pbName + ' (processBytes)');
    } catch (e) { report('processBytes hook failed: ' + e); }
  }
  if (dfName) {
    try {
      CCM[dfName].overload('[B', 'int').implementation = function (ob, oo) {
        var r = this[dfName](ob, oo);
        var pt = PENDING_IN; PENDING_IN = '';
        report('doFinal: in=' + (pt || '(none)') + '  out=' + jbytesRangeHex(ob, oo, r) + '  (wrote ' + r + 'B @' + oo + ')');
        return r;
      };
      report('hooked ' + dfName + ' (doFinal)');
    } catch (e) { report('doFinal hook failed: ' + e); }
  }

  if (initName) {
    try {
      CCM[initName].overload('boolean', 'org.bouncycastle.crypto.CipherParameters').implementation =
        function (forEnc, params) {
          report('=== init(forEncryption=' + forEnc + ') params: ===');
          try { dumpFields(params, '  ', 2); } catch (e) { report('  dump err: ' + e); }
          return this[initName](forEnc, params);
        };
      report('hooked ' + initName + ' (init)');
    } catch (e) {
      // fallback: overload by discovered param type name
      try {
        var im = null;
        for (var k = 0; k < methods.length; k++) if (methods[k].getName() === initName) im = methods[k];
        var ptname = im.getParameterTypes()[1].getName();
        CCM[initName].overload('boolean', ptname).implementation = function (forEnc, params) {
          report('=== init(forEncryption=' + forEnc + ') params: ===');
          try { dumpFields(params, '  ', 2); } catch (e2) { report('  dump err: ' + e2); }
          return this[initName](forEnc, params);
        };
        report('hooked ' + initName + ' (init, via ' + ptname + ')');
      } catch (e3) { report('init hook failed: ' + e3); }
    }
  } else { report('could not resolve init'); }

  if (ppName) {
    try {
      CCM[ppName].overload('[B', 'int', 'int').implementation = function (buf, off, len) {
        var inHex = jbytesRangeHex(buf, off, len);
        var out = this[ppName](buf, off, len);
        report('processPacket in(' + len + ')  = ' + inHex);
        report('processPacket out(' + (out ? out.length : 0) + ') = ' + jbytesToHex(out));
        report('caller: ' + shortBacktrace());
        return out;
      };
      report('hooked ' + ppName + ' (processPacket)');
    } catch (e) { report('processPacket hook failed: ' + e); }
  } else { report('could not resolve processPacket'); }

  report('ready — trigger a voice-pack (language OTA) download in the app now.');
});
