// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
// Noncommercial use only; any commercial or for-profit use requires a separate
// written license from the copyright holder. See the LICENSE file for the terms.

// Native BoringSSL SSL_read/SSL_write hook — FULL HEX dump (not lossy ASCII),
// tagged by the SSL* connection pointer, for offline HTTP/2+HPACK reassembly.
// Safe under SecNeo (native only, no Java/ART touch). Writes to a file, not
// console.log (a fast console.log stream stalls the app's main thread).
'use strict';

var OUT_PATH = '/sdcard/Android/data/com.lumiunited.aqarahome.play/files/sslfull.log';
var f = null;
try {
    f = new File(OUT_PATH, 'ab');
} catch (e) {
    f = new File('/data/local/tmp/sslfull.log', 'ab');
}

function writeLine(s) {
    try {
        f.write(s + '\n');
        f.flush();
    } catch (e) { /* best-effort */ }
}

function toHex(bytes) {
    var arr = new Uint8Array(bytes);
    var out = new Array(arr.length);
    for (var i = 0; i < arr.length; i++) {
        out[i] = ('0' + arr[i].toString(16)).slice(-2);
    }
    return out.join('');
}

var hookedModules = {};

function hookModule(m) {
    if (hookedModules[m.name]) return;
    var readPtr = Module.findExportByName(m.name, 'SSL_read');
    var writePtr = Module.findExportByName(m.name, 'SSL_write');
    if (!readPtr && !writePtr) return;
    hookedModules[m.name] = true;
    if (readPtr) {
        try {
            Interceptor.attach(readPtr, {
                onEnter: function (args) { this.ssl = args[0]; this.buf = args[1]; },
                onLeave: function (retval) {
                    var n = retval.toInt32();
                    if (n > 0) {
                        try {
                            var data = Memory.readByteArray(this.buf, n);
                            writeLine('==== ' + Date.now() + ' SSL_read [' + m.name + '] ssl=' + this.ssl + ' len=' + n + ' ====');
                            writeLine(toHex(data));
                        } catch (e) { writeLine('read err ' + e); }
                    }
                }
            });
        } catch (e) { /* ignore */ }
    }
    if (writePtr) {
        try {
            Interceptor.attach(writePtr, {
                onEnter: function (args) {
                    var ssl = args[0];
                    var len = args[2].toInt32();
                    if (len > 0) {
                        try {
                            var data = Memory.readByteArray(args[1], len);
                            writeLine('==== ' + Date.now() + ' SSL_write [' + m.name + '] ssl=' + ssl + ' len=' + len + ' ====');
                            writeLine(toHex(data));
                        } catch (e) { writeLine('write err ' + e); }
                    }
                }
            });
        } catch (e) { /* ignore */ }
    }
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookModule);
    writeLine('[*] sslfull hook installed across ' + Object.keys(hookedModules).length + ' modules: ' + Object.keys(hookedModules).join(','));
}, 0);

['dlopen', 'android_dlopen_ext'].forEach(function (name) {
    var addr = Module.findExportByName(null, name);
    if (!addr) return;
    Interceptor.attach(addr, {
        onLeave: function () {
            setTimeout(function () {
                Process.enumerateModules().forEach(hookModule);
            }, 50);
        }
    });
});
