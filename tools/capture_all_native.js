// ============================================================================
// capture_all_native.js  —  C-stage-1 capture infrastructure
//
// ONE native-only Frida hook (never touches Java/ART → safe under SecNeo, same
// class as capture_ssl_native_frida17.js) that records, to SEPARATE per-category
// files on-device, everything C-stage-1 covers:
//
//   https.log    every SSL_read/SSL_write across every module that exports them
//                (libssl.so + libjavacrypto.so = OkHttp/conscrypt; the app's
//                other TLS stack, Cronet's libcrypto_httpengine.so, is stripped
//                and exports no SSL_read/SSL_write, so it is NOT hookable by
//                symbol — confirmed 2026-09-02; the API traffic we care about
//                rides OkHttp anyway). FULL HEX, tagged by SSL* pointer +
//                direction, for offline HTTP/2+HPACK reassembly via decode_h2.py.
//   modules.log  every dlopen/android_dlopen_ext → which .so loads and WHEN
//                (reveals lazy-loaded libs, e.g. liblumidevsdk.so appears only
//                after the main screen; a crypto lib appearing right as BLE
//                connects tells us what feature uses it).
//
// C-stage-2 (liblumidevsdk crypto/sign hooks: getSignHead, aesEncryptedContent,
// getEncryptedData, ...) is deliberately NOT here yet — those need their C
// signatures reversed from LIVE calls before they can be read safely, so they
// get built when we actually run B (sign fires on every cloud call) / the BLE
// work (aes fires on BLE), not blind. See docs/reference/native-libs.md.
//
// ATTACH via the Frida Python API (NOT run_hook.py — its PTY wrapper has hung
// repeatedly). Keep the process alive with time.sleep. Pull the per-category
// files afterwards and decode https.log with tools/decode_h2.py.
// ============================================================================
'use strict';

var OUT_DIR = '/sdcard/Android/data/com.lumiunited.aqarahome.play/files/cap';
var files = {};

function openFile(cat) {
    if (files[cat]) return files[cat];
    var f = null;
    try { f = new File(OUT_DIR + '/' + cat + '.log', 'ab'); }
    catch (e) {
        try { f = new File('/data/local/tmp/cap_' + cat + '.log', 'ab'); } catch (e2) { f = null; }
    }
    files[cat] = f;
    return f;
}

function W(cat, s) {
    var f = openFile(cat);
    if (!f) return;
    try { f.write(s + '\n'); f.flush(); } catch (e) { /* best-effort */ }
}

function toHex(bytes) {
    var arr = new Uint8Array(bytes);
    var out = new Array(arr.length);
    for (var i = 0; i < arr.length; i++) out[i] = ('0' + arr[i].toString(16)).slice(-2);
    return out.join('');
}

// ---- HTTPS: SSL_read / SSL_write across every module that exports them -------
var hookedSSL = {};
function hookSSL(m) {
    if (hookedSSL[m.name]) return;
    var readPtr, writePtr;
    try { readPtr = m.findExportByName('SSL_read'); } catch (e) { readPtr = null; }
    try { writePtr = m.findExportByName('SSL_write'); } catch (e) { writePtr = null; }
    if (!readPtr && !writePtr) return;
    hookedSSL[m.name] = true;
    if (readPtr) {
        try {
            Interceptor.attach(readPtr, {
                onEnter: function (args) { this.ssl = args[0]; this.buf = args[1]; },
                onLeave: function (retval) {
                    var n = retval.toInt32();
                    if (n <= 0) return;
                    try {
                        var data = this.buf.readByteArray(n);
                        W('https', '==== ' + Date.now() + ' SSL_read [' + m.name + '] ssl=' + this.ssl + ' len=' + n + ' ====');
                        W('https', toHex(data));
                    } catch (e) { W('https', 'read err ' + e); }
                }
            });
        } catch (e) { W('https', 'attach read err ' + e); }
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
                        W('https', '==== ' + Date.now() + ' SSL_write [' + m.name + '] ssl=' + ssl + ' len=' + len + ' ====');
                        W('https', toHex(data));
                    } catch (e) { W('https', 'write err ' + e); }
                }
            });
        } catch (e) { W('https', 'attach write err ' + e); }
    }
}

// ---- MODULES: dlopen / android_dlopen_ext trace -----------------------------
function traceDlopen() {
    ['dlopen', 'android_dlopen_ext'].forEach(function (name) {
        var addr = null;
        try { addr = Process.getModuleByName('libc.so').findExportByName(name); } catch (e) { addr = null; }
        if (!addr) return;
        Interceptor.attach(addr, {
            onEnter: function (args) {
                try { this.path = args[0].readUtf8String(); } catch (e) { this.path = '<?>'; }
            },
            onLeave: function () {
                if (this.path) W('modules', Date.now() + ' dlopen ' + this.path);
                // a newly-loaded module may export SSL_read/write — re-scan
                setTimeout(function () { Process.enumerateModules().forEach(hookSSL); }, 50);
            }
        });
    });
}

setTimeout(function () {
    Process.enumerateModules().forEach(hookSSL);
    traceDlopen();
    var msg = 'capture_all_native installed | SSL modules: ' + Object.keys(hookedSSL).join(',') + ' | OUT_DIR=' + OUT_DIR;
    W('https', '[*] ' + msg);
    W('modules', '[*] ' + msg);
    send(msg);
}, 0);
