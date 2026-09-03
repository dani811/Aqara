// Frida-17 port of sslfull.js (Frida 17 removed the static
// Module.findExportByName(moduleName, exportName) API — see
// capture_ssl_native_frida17.js's own header comment / frida-repack-strategy
// memory). Native BoringSSL SSL_read/SSL_write hook — FULL HEX dump (not
// lossy ASCII), tagged by the SSL* connection pointer, for offline HTTP/2 +
// HPACK reassembly via decode_h2.py. Never touches Java/ART — safe under
// SecNeo (confirmed all session: zero crashes from any native-only hook,
// vs. two crashes tonight from active Java method-override hooks).
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
                    if (n > 0) {
                        try {
                            var data = this.buf.readByteArray(n);
                            writeLine('==== ' + Date.now() + ' SSL_read [' + m.name + '] ssl=' + this.ssl + ' len=' + n + ' ====');
                            writeLine(toHex(data));
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
                    var ssl = args[0];
                    var len = args[2].toInt32();
                    if (len > 0) {
                        try {
                            var data = args[1].readByteArray(len);
                            writeLine('==== ' + Date.now() + ' SSL_write [' + m.name + '] ssl=' + ssl + ' len=' + len + ' ====');
                            writeLine(toHex(data));
                        } catch (e) { writeLine('write err ' + e); }
                    }
                }
            });
        } catch (e) { writeLine('attach write err ' + e); }
    }
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookModule);
    writeLine('[*] sslfull hook installed across ' + Object.keys(hookedModules).length + ' modules: ' + Object.keys(hookedModules).join(','));
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
