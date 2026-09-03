// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

// Frida-17 native BoringSSL hook, FILTERED — only dumps SSL_read/SSL_write
// buffers whose plaintext contains one of MATCH[] (path/keyword fragments).
//
// WHY THIS EXISTS (learned the hard way, repeatedly): the full-dump
// sslfull_frida17.js writes to disk on EVERY SSL_read/SSL_write, synchronously,
// on the app's own thread. On a light API screen that's fine. On a TLS-heavy
// screen — above all the LOGIN screen, which is a WebView firing hundreds of
// TLS calls — the per-call synchronous file write STALLS the main thread and
// the screen goes solid black / frozen (looks like a crash, isn't one). This
// is the same failure frida-setup.md and capture_ssl_native_frida17.js already
// warn about ("stall the app's main thread", "app freezes solid"). The fix is
// to write only for the few requests we actually want — a substring filter
// before writeLine cuts hundreds of writes down to two or three.
//
// Never touches Java/ART — safe under SecNeo, like every native-only hook.
//
// USAGE: edit MATCH below for the request(s) you want, then attach via the
// Frida Python API (NOT run_hook.py):
//   python3 -c "import frida,time; \
//     dev=frida.get_device_manager().add_remote_device('127.0.0.1:27042'); \
//     s=dev.attach('Gadget'); sc=s.create_script(open('tools/sslfilter_frida17.js').read()); \
//     sc.load(); time.sleep(600)"
// Log lands on-device at OUT_PATH; pull + decode with tools/decode_h2.py.
'use strict';

// Substring(s) to look for in each SSL buffer's plaintext. A buffer is dumped
// if ANY of these appears in it. Keep this tight — the whole point is few writes.
var MATCH = ['guard-code/login', '/user/', '/lumi/dev/bluetooth/lock/'];

var OUT_PATH = '/sdcard/Android/data/com.lumiunited.aqarahome.play/files/sslfilter.log';
var f = null;
try {
    f = new File(OUT_PATH, 'ab');
} catch (e) {
    f = new File('/data/local/tmp/sslfilter.log', 'ab');
}

function writeLine(s) {
    try { f.write(s + '\n'); f.flush(); } catch (e) { /* best-effort */ }
}

function toHex(bytes) {
    var arr = new Uint8Array(bytes);
    var out = new Array(arr.length);
    for (var i = 0; i < arr.length; i++) out[i] = ('0' + arr[i].toString(16)).slice(-2);
    return out.join('');
}

// Cheap ASCII scan of the buffer for any MATCH substring, WITHOUT allocating a
// full string dump of huge buffers first: decode to a bounded ASCII preview.
function matches(bytes) {
    var arr = new Uint8Array(bytes);
    var n = arr.length;
    var s = '';
    for (var i = 0; i < n; i++) {
        var b = arr[i];
        s += (b >= 9 && b < 127) ? String.fromCharCode(b) : '.';
        // headers/path live near the front of an HTTP/2 HEADERS frame; cap the
        // scan so a multi-MB body doesn't cost a multi-MB string build.
        if (s.length > 4096) break;
    }
    for (var j = 0; j < MATCH.length; j++) if (s.indexOf(MATCH[j]) !== -1) return true;
    return false;
}

var hookedModules = {};

function hookModule(m) {
    if (hookedModules[m.name]) return;
    var readPtr, writePtr;
    try { readPtr = m.findExportByName('SSL_read'); } catch (e) { readPtr = null; }
    try { writePtr = m.findExportByName('SSL_write'); } catch (e) { writePtr = null; }
    if (!readPtr && !writePtr) return;
    hookedModules[m.name] = true;
    if (readPtr) {
        try {
            Interceptor.attach(readPtr, {
                onEnter: function (args) { this.ssl = args[0]; this.buf = args[1]; },
                onLeave: function (retval) {
                    var n = retval.toInt32();
                    if (n <= 0) return;
                    try {
                        var data = this.buf.readByteArray(n);
                        if (!matches(data)) return;
                        writeLine('==== ' + Date.now() + ' SSL_read [' + m.name + '] ssl=' + this.ssl + ' len=' + n + ' ====');
                        writeLine(toHex(data));
                    } catch (e) { writeLine('read err ' + e); }
                }
            });
        } catch (e) { writeLine('attach read err ' + e); }
    }
    if (writePtr) {
        try {
            Interceptor.attach(writePtr, {
                onEnter: function (args) {
                    var ssl = args[0];
                    var len = args[2].toInt32();
                    if (len <= 0) return;
                    try {
                        var data = args[1].readByteArray(len);
                        if (!matches(data)) return;
                        writeLine('==== ' + Date.now() + ' SSL_write [' + m.name + '] ssl=' + ssl + ' len=' + len + ' ====');
                        writeLine(toHex(data));
                    } catch (e) { writeLine('write err ' + e); }
                }
            });
        } catch (e) { writeLine('attach write err ' + e); }
    }
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookModule);
    writeLine('[*] sslfilter hook installed across ' + Object.keys(hookedModules).length + ' modules: ' + Object.keys(hookedModules).join(',') + ' | MATCH=' + JSON.stringify(MATCH));
    send('installed(filtered): ' + Object.keys(hookedModules).join(','));
}, 0);

['dlopen', 'android_dlopen_ext'].forEach(function (name) {
    var addr = null;
    try { addr = Process.getModuleByName('libc.so').findExportByName(name); } catch (e) { addr = null; }
    if (!addr) return;
    Interceptor.attach(addr, {
        onLeave: function () {
            setTimeout(function () { Process.enumerateModules().forEach(hookModule); }, 50);
        }
    });
});
