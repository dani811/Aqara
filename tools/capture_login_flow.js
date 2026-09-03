// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

"use strict";
// ============================================================================
// CAPTURA DEL LOGIN DE CUENTA (la que nunca se hizo)
//
// CONTEXTO: `kdf.login` cifra la contrasena EN CRUDO con la RSA-1024 y el
// servidor contesta SIEMPRE code=810 ("Password incorrect"), incluso con
// credenciales que la app acepta. El 810 se habia tomado como prueba de que el
// sobre criptografico era correcto -- pero una cuenta INEXISTENTE devuelve ese
// mismo 810, asi que no demuestra nada. Nunca se ha visto salir un token.
//
// OBJETIVO: ver que hace la app REALMENTE en un login de cuenta, en concreto:
//   1. Que PLAINTEXT entra en el RSA. Si es la contrasena tal cual, nuestro
//      formato es correcto y el fallo esta en otra parte. Si es un digest (32
//      chars hex = MD5, 64 = SHA-256), con o sin sal/timestamp, ahi esta la
//      causa del 810 permanente.                                    <-- clave A
//   2. A que URL va el login y con que headers. Puede que
//      /user/guard-code/login sea la variante con segundo factor y que el login
//      normal viva en otra ruta.                                    <-- clave B
//   3. El body JSON EN CLARO antes del AES-128-GCM (campos que no mandamos).
//   4. Cualquier MessageDigest sobre algo corto: pilla el hash de la contrasena
//      aunque ocurra lejos del Cipher.
//
// USO:
//   1. Cerrar la app (force-stop). Lanzar el hook ANTES de reabrirla:
//        python3 tools/run_hook.py tools/capture_login_flow.js \
//          --host <ip-del-movil>:<puerto> > /tmp/loginflow.log 2>&1 &
//      (el 1er enganche suele dar "connection closed"; reintentar una vez)
//   2. Abrir la app y hacer UN login de cuenta completo (usuario + contrasena).
//   3. Cortar el hook y extraer:
//        grep -E "LOGINFLOW.*(RSA_IN|LOGIN_REQ|LOGIN_BODY|DIGEST|AES_PLAIN)" \
//          /tmp/loginflow.log
//
// AVISO: este log contiene tu contrasena en claro (ese es justo el punto).
// Vive en /tmp, no en el repo. Borralo en cuanto extraigas la conclusion.
// ============================================================================
setInterval(function () {}, 5000);

function L(s) { console.log("LOGINFLOW ts=" + Date.now() + " " + s); }

function jbytes2h(arr) {
  if (!arr) return "<null>";
  try {
    var a = Java.array("byte", arr), s = "";
    for (var i = 0; i < a.length; i++) s += ("0" + (a[i] & 0xff).toString(16)).slice(-2);
    return s;
  } catch (e) { return "<err:" + e + ">"; }
}

function jbytes2utf8(arr) {
  if (!arr) return "<null>";
  try {
    return String(Java.use("java.lang.String").$new(arr, "UTF-8"));
  } catch (e) { return "<no-utf8>"; }
}

function jbytes2b64(arr) {
  if (!arr) return "<null>";
  try {
    return String(Java.use("android.util.Base64").encodeToString(arr, 2));  // NO_WRAP
  } catch (e) { return "<err:" + e + ">"; }
}

// Un digest se delata por la longitud del plaintext: 32 = MD5 hex,
// 40 = SHA-1 hex, 64 = SHA-256 hex. Se anota para leer el log de un vistazo.
function shapeOf(s) {
  if (s === null || s === undefined) return "?";
  var hex = /^[0-9a-fA-F]+$/.test(s);
  if (hex && s.length === 32) return "PARECE MD5-hex";
  if (hex && s.length === 40) return "PARECE SHA1-hex";
  if (hex && s.length === 64) return "PARECE SHA256-hex";
  if (hex) return "hex de " + s.length;
  return "texto plano de " + s.length + " chars";
}

Java.perform(function () {
  var hooked = [];

  // ---- CLAVE A: que entra en el RSA -------------------------------------
  // La captura original hookeo el OUTPUT de doFinal (para sacar la clave
  // publica). Aqui queremos el INPUT, que es justo lo que nadie miro.
  try {
    var Cipher = Java.use("javax.crypto.Cipher");
    Cipher.doFinal.overload("[B").implementation = function (input) {
      var out = this.doFinal(input);
      try {
        var alg = "";
        try { alg = String(this.getAlgorithm()); } catch (_) { alg = "<?>"; }
        var outLen = out ? out.length : -1;
        // RSA-1024 -> 128 bytes de salida. Filtramos por eso o por el nombre.
        if (alg.toUpperCase().indexOf("RSA") !== -1 || outLen === 128) {
          var txt = jbytes2utf8(input);
          L("RSA_IN alg=" + alg + " inLen=" + input.length + " outLen=" + outLen);
          L("RSA_IN_UTF8 " + txt);
          L("RSA_IN_SHAPE " + shapeOf(txt));
          L("RSA_IN_HEX " + jbytes2h(input));
          L("RSA_OUT_B64 " + jbytes2b64(out));
        }
      } catch (_) {}
      return out;
    };
    hooked.push("Cipher.doFinal(input)");
  } catch (e) { console.log("LOGINFLOW_ERR cipher " + e); }

  // ---- CLAVE B: a que URL va el login, con que headers y que body --------
  try {
    var RB = Java.use("okhttp3.Request$Builder");
    RB.build.overload().implementation = function () {
      var req = this.build();
      try {
        var url = String(req.url());
        // "login" tambien casa con /dev/bluetooth/login/assure/*, que NO es
        // esto; se marcan aparte para no confundirlos en el log.
        var isBle = url.indexOf("/bluetooth/login/") !== -1;
        var isAuth = !isBle && (url.indexOf("login") !== -1 ||
                                url.indexOf("guard-code") !== -1 ||
                                url.indexOf("/user/") !== -1 ||
                                url.indexOf("token") !== -1);
        if (isAuth) {
          var hdrs = req.headers(), hlines = [];
          for (var i = 0; i < hdrs.size(); i++) {
            hlines.push(String(hdrs.name(i)) + ": " + String(hdrs.value(i)));
          }
          var bodyStr = "<none>";
          try {
            var body = req.body();
            if (body !== null) {
              var Buffer = Java.use("okio.Buffer");
              var buf = Buffer.$new();
              body.writeTo(buf);
              bodyStr = String(buf.readUtf8());
            }
          } catch (be) { bodyStr = "<body-err:" + be + ">"; }
          L("LOGIN_REQ " + String(req.method()) + " " + url);
          L("LOGIN_HEADERS " + JSON.stringify(hlines));
          L("LOGIN_BODY " + bodyStr);   // cifrado (x-aes128gcm); el claro va abajo
        }
      } catch (_) {}
      return req;
    };
    hooked.push("okhttp.request");
  } catch (e) { console.log("LOGINFLOW_ERR request " + e); }

  try {
    var RespBody = Java.use("okhttp3.ResponseBody");
    RespBody.string.implementation = function () {
      var s = this.string();
      try {
        if (s && s.length < 4000) L("LOGIN_RESP " + s.slice(0, 2000));
      } catch (_) {}
      return s;
    };
    hooked.push("okhttp.response");
  } catch (e) { console.log("LOGINFLOW_ERR response " + e); }

  // ---- El body EN CLARO, antes del AES-128-GCM ---------------------------
  // El cifrado vive en el SDK nativo (LumiDevSDK.aesEncryptedContent segun las
  // notas de RE). Buscamos la clase entre las cargadas en vez de fijar el
  // paquete, que cambia entre versiones de la app.
  try {
    var found = [];
    Java.enumerateLoadedClassesSync().forEach(function (name) {
      if (name.indexOf("LumiDevSDK") !== -1) found.push(name);
    });
    L("SDK_CLASSES " + JSON.stringify(found));
    found.forEach(function (name) {
      try {
        var K = Java.use(name);
        Object.getOwnPropertyNames(K).forEach(function (m) {
          if (m.toLowerCase().indexOf("aesencrypted") === -1) return;
          K[m].overloads.forEach(function (ov) {
            ov.implementation = function () {
              try {
                for (var i = 0; i < arguments.length; i++) {
                  var a = arguments[i];
                  if (typeof a === "string" && a.length < 3000) {
                    L("AES_PLAIN arg" + i + " " + a);
                  }
                }
              } catch (_) {}
              return ov.apply(this, arguments);
            };
          });
          hooked.push(name + "." + m);
        });
      } catch (_) {}
    });
  } catch (e) { console.log("LOGINFLOW_ERR sdk " + e); }

  // ---- Cualquier digest sobre algo corto (pilla un MD5/SHA de la clave) ---
  try {
    var MD = Java.use("java.security.MessageDigest");
    MD.digest.overload("[B").implementation = function (inp) {
      var out = this.digest(inp);
      try {
        if (inp && inp.length > 0 && inp.length < 200) {
          L("DIGEST alg=" + String(this.getAlgorithm()) +
            " in=" + jbytes2utf8(inp) + " out=" + jbytes2h(out));
        }
      } catch (_) {}
      return out;
    };
    hooked.push("MessageDigest.digest");
  } catch (e) { console.log("LOGINFLOW_ERR digest " + e); }

  console.log("LOGINFLOW_HOOKED " + JSON.stringify(hooked));
  console.log("LOGINFLOW_READY " + Date.now());
});
