// Native BoringSSL SSL_read/SSL_write hook — stable under SecNeo's runtime
// anti-Frida (never touches the Java/ART bridge, unlike a Java okhttp hook,
// which crashes after a few minutes per specs/037-cloud-session-mitm/spec.md).
// Dumps plaintext HTTP bodies (pre-encryption on write, post-decryption on read)
// to a FILE on-device, not console.log/PTY — a fast stream of console.log calls
// over the PTY was observed (2026-08-28) to stall the app's main thread badly
// enough to look like an ANR, and repeated attach/detach cycles seem to trip
// something in SecNeo's protection (app freezes solid, needs a full relaunch).
// Attach ONCE, leave it running for the whole session, read the file whenever.
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
    var readPtr = Module.findExportByName(m.name, 'SSL_read');
    var writePtr = Module.findExportByName(m.name, 'SSL_write');
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
                            var data = Memory.readByteArray(this.buf, n);
                            writeLine('==== ' + Date.now() + ' SSL_read [' + m.name + '] ' + n + ' bytes ====');
                            writeLine(dumpText(data));
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
                    var len = args[2].toInt32();
                    if (len > 0) {
                        try {
                            var data = Memory.readByteArray(args[1], len);
                            writeLine('==== ' + Date.now() + ' SSL_write [' + m.name + '] ' + len + ' bytes ====');
                            writeLine(dumpText(data));
                        } catch (e) { writeLine('write err ' + e); }
                    }
                }
            });
        } catch (e) { /* ignore */ }
    }
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookModule);
    writeLine('[*] SSL hook installed across ' + Object.keys(hookedModules).length + ' modules: ' + Object.keys(hookedModules).join(','));
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
