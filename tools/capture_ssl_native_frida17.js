// Native BoringSSL SSL_read/SSL_write hook — stable under SecNeo's runtime
// anti-Frida (never touches the Java/ART bridge, unlike a Java okhttp hook,
// which crashes after a few minutes per specs/037-cloud-session-mitm/spec.md).
// Dumps plaintext HTTP bodies (pre-encryption on write, post-decryption on read)
// to a FILE on-device, not console.log/PTY — a fast stream of console.log calls
// over the PTY was observed (2026-08-28) to stall the app's main thread badly
// enough to look like an ANR, and repeated attach/detach cycles seem to trip
// something in SecNeo's protection (app freezes solid, needs a full relaunch).
// Attach ONCE, leave it running for the whole session, read the file whenever.
//
// This is a Frida-17.x port of capture_ssl_native.js: Frida 17 removed the
// static `Module.findExportByName(moduleName, exportName)` API entirely (see
// frida-repack-strategy.md — same release line that unbundled frida-java-bridge
// from core). The per-Module instance method still exists — use
// `Process.getModuleByName(name).findExportByName(export)` instead. Same
// applies to the dlopen/android_dlopen_ext re-hook at the bottom. If
// capture_ssl_native.js throws "TypeError: not a function" at
// Module.findExportByName, the host is on Frida 17+ and this file is the one
// to use instead.
'use strict';

var OUT_PATH = '/sdcard/Android/data/com.lumiunited.aqarahome.play/files/ssl_capture.log';
var f = null;
try {
    f = new File(OUT_PATH, 'ab');
} catch (e) {
    // fall back to app-internal-ish path some devices allow; still no console.log spam
    f = new File('/data/local/tmp/ssl_capture.log', 'ab');
}

function writeLine(s) {
    try {
        f.write(s + '\n');
        f.flush();
    } catch (e) { /* best-effort; never throw from a hook */ }
}

function dumpText(bytes) {
    var arr = new Uint8Array(bytes);
    var s = '';
    for (var i = 0; i < arr.length; i++) {
        var b = arr[i];
        s += (b >= 9 && b < 127) ? String.fromCharCode(b) : '.';
    }
    return s;
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
                onEnter: function (args) { this.buf = args[1]; },
                onLeave: function (retval) {
                    var n = retval.toInt32();
                    if (n > 0) {
                        try {
                            var data = this.buf.readByteArray(n);
                            writeLine('==== ' + Date.now() + ' SSL_read [' + m.name + '] ' + n + ' bytes ====');
                            writeLine(dumpText(data));
                        } catch (e) { writeLine('read err ' + e); }
                    }
                }
            });
        } catch (e) { writeLine('attach read err ' + e); }
    }
    if (writePtr) {
        try {
            Interceptor.attach(writePtr, {
                onEnter: function (args) {
                    var len = args[2].toInt32();
                    if (len > 0) {
                        try {
                            var data = args[1].readByteArray(len);
                            writeLine('==== ' + Date.now() + ' SSL_write [' + m.name + '] ' + len + ' bytes ====');
                            writeLine(dumpText(data));
                        } catch (e) { writeLine('write err ' + e); }
                    }
                }
            });
        } catch (e) { writeLine('attach write err ' + e); }
    }
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookModule);
    writeLine('[*] SSL hook installed across ' + Object.keys(hookedModules).length + ' modules: ' + Object.keys(hookedModules).join(','));
    send('installed: ' + Object.keys(hookedModules).join(','));
}, 0);

['dlopen', 'android_dlopen_ext'].forEach(function (name) {
    var addr = null;
    try {
        var libc = Process.getModuleByName('libc.so');
        addr = libc.findExportByName(name);
    } catch (e) { addr = null; }
    if (!addr) return;
    Interceptor.attach(addr, {
        onLeave: function () {
            setTimeout(function () {
                Process.enumerateModules().forEach(hookModule);
            }, 50);
        }
    });
});
