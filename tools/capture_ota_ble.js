// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

'use strict';
// Frida 17: the Java bridge is no longer a global — bundle it via frida-compile.
// Build:  frida-compile tools/capture_ota_ble.js -o tools/capture_ota_ble.agent.js
// Load :  python tools/frida_attach.py tools/capture_ota_ble.agent.js --seconds N
import Java from 'frida-java-bridge';

// Capture the U200 language-OTA transfer on the BLE side.
//
// Hooks every write to the OTA characteristic ff91 (ATT handle 0x3c) and:
//   - counts chunks and logs a compact head of each frame (prefix + first bytes),
//   - dumps the FULL payload + a Java backtrace for the two frames that matter
//     for a from-scratch builder: the init frame (prefix 0x11, carries the
//     filename+size) and the activation frame (prefix 0x90, the per-app-process
//     token whose origin we still need to locate).
//
// The backtrace on the 0x90 frame is the whole point of this pass: it shows the
// call site that assembled/sent that value, so we can then hook its generator.
//
// Load via: python tools/frida_attach.py tools/capture_ota_ble.js --seconds N
// (send() payloads print prefixed MSG: on the host).

function hx(bytes, max) {
  var n = (max && bytes.length > max) ? max : bytes.length;
  var s = '';
  for (var i = 0; i < n; i++) {
    var b = bytes[i] & 0xff;
    s += (b < 16 ? '0' : '') + b.toString(16);
  }
  if (n < bytes.length) s += '…(+' + (bytes.length - n) + ')';
  return s;
}

// Java byte[] (signed) -> JS array of ints
function toArr(jbytes) {
  var out = [];
  if (jbytes === null) return out;
  var len = jbytes.length;
  for (var i = 0; i < len; i++) out.push(jbytes[i]);
  return out;
}

Java.perform(function () {
  var Log = Java.use('android.util.Log');
  var Throwable = Java.use('java.lang.Throwable');
  function backtrace() {
    return Log.getStackTraceString(Throwable.$new());
  }

  var chunkCount = 0;
  var byteCount = 0;
  var sawInit = false;

  function isOta(charObj) {
    try {
      return charObj.getUuid().toString().toLowerCase().indexOf('ff91') !== -1;
    } catch (e) {
      return false;
    }
  }

  function report(tag, charObj, jbytes) {
    if (!isOta(charObj)) return;
    var bytes = toArr(jbytes);
    if (bytes.length === 0) return;
    var prefix = bytes[0] & 0xff;
    chunkCount++;
    byteCount += bytes.length;

    // The init frame: prefix 0x11 and readable ASCII (the filename). Dump once.
    var looksInit = (prefix === 0x11 && bytes.length > 20 && !sawInit &&
                     bytes[3] >= 0x20 && bytes[3] < 0x7f);
    if (looksInit) {
      sawInit = true;
      send({ t: 'OTA_INIT', tag: tag, len: bytes.length, full: hx(bytes) });
    }

    // The activation frame: prefix 0x90. Dump full + backtrace every time.
    if (prefix === 0x90) {
      send({ t: 'OTA_0x90', tag: tag, seq: chunkCount, len: bytes.length,
             full: hx(bytes), backtrace: backtrace() });
    }

    // Heartbeat: first 3 chunks verbatim, then every 500th, so we can see the
    // transfer flowing without flooding.
    if (chunkCount <= 3 || (chunkCount % 500) === 0) {
      send({ t: 'ota_chunk', tag: tag, seq: chunkCount, len: bytes.length,
             prefix: prefix.toString(16), head: hx(bytes, 24) });
    }
  }

  // --- Android framework BLE write paths (RN BLE libs funnel through these) ---
  var Gatt = Java.use('android.bluetooth.BluetoothGatt');

  // Legacy: setValue([B) then writeCharacteristic(char) sends the cached value.
  try {
    var w1 = Gatt.writeCharacteristic.overload('android.bluetooth.BluetoothGattCharacteristic');
    w1.implementation = function (c) {
      try { report('write(char)', c, c.getValue()); } catch (e) {}
      return w1.call(this, c);
    };
    send({ t: 'hook', m: 'writeCharacteristic(char) hooked' });
  } catch (e) {
    send({ t: 'warn', m: 'no legacy writeCharacteristic: ' + e });
  }

  // API 33+: writeCharacteristic(char, [B, int) passes the bytes directly.
  try {
    var w2 = Gatt.writeCharacteristic.overload(
      'android.bluetooth.BluetoothGattCharacteristic', '[B', 'int');
    w2.implementation = function (c, val, wt) {
      try { report('write(char,val,wt)', c, val); } catch (e) {}
      return w2.call(this, c, val, wt);
    };
    send({ t: 'hook', m: 'writeCharacteristic(char,val,wt) hooked' });
  } catch (e) {
    send({ t: 'warn', m: 'no API33 writeCharacteristic: ' + e });
  }

  // Periodic totals so the host sees progress and the final tally.
  setInterval(function () {
    if (chunkCount > 0) {
      send({ t: 'totals', chunks: chunkCount, bytes: byteCount });
    }
  }, 5000);

  send({ t: 'ready', m: 'OTA ff91 capture armed — trigger the language download now' });
});
