// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

"use strict";
// ============================================================================
// TEST DE REPLAY CRUZADO -- PASO 1 (captura desde la app REAL)
// Ver docs/reference/.
//
// OBJETIVO: capturar, de una sola operación de bloqueo/desbloqueo real con la
// app oficial, TODO lo que la app hace en el handshake 0610, para poder (a)
// COMPARARLO con lo que produce nuestro kdf.py, y (b) REINYECTARLO tal cual
// desde el ESP32/Bumble (tools/bumble_replay.py) y ver si el muro cae.
//
// Captura, con timestamp de milisegundo en CADA línea (para poder ordenar la
// carrera temporal exacta entre nube y BLE):
//   1. Petición HTTP a /dev/bluetooth/login/assure/publickey  (método, URL,
//      TODOS los headers, body) + su RESPUESTA (cloudPublicKey).  <-- clave A
//   2. Petición HTTP a /dev/bluetooth/login/assure/verify + respuesta
//      (sessionKey/nonce/verifyData).
//   3. Las escrituras GATT EXACTAS por ff07 (fragmentos 5a.. del frame 0610 y
//      del 0710) -- bytes crudos, tal cual salen al aire.               <-- clave B
//   4. Las notificaciones GATT por ff08 (da.. -- respuesta del lock, para
//      confirmar que ESTA sesión de la app SÍ obtuvo pubkey real -> control).
//
// USO:
//   1. adb -s <serie> forward tcp:27042 tcp:27042
//   2. cerrar app (force-stop), lanzar este hook ANTES de reabrir:
//        python3 tools/run_hook.py tools/capture_publickey_flow.js  > /tmp/pkflow.log 2>&1 &
//      (recordar: el 1er intento de enganche suele dar "connection closed";
//       reintentar una vez, patrón conocido -- §11.46)
//   3. abrir app, ficha del U200, UNA operación de bloqueo/desbloqueo real.
//   4. cortar el hook. Extraer del log:
//        grep -E "PKFLOW_(PUBKEY_REQ|PUBKEY_RESP|VERIFY|FF07|FF08)" /tmp/pkflow.log
//
// La pantalla del móvil SIEMPRE encendida durante la operación (la app pausa
// el BLE con la pantalla apagada).
// ============================================================================
setInterval(function () {}, 5000);

function L(s) { console.log("PKFLOW ts=" + Date.now() + " " + s); }

function jbytes2h(arr) {
  if (!arr) return "<null>";
  try {
    var a = Java.array("byte", arr), s = "";
    for (var i = 0; i < a.length; i++) s += ("0" + (a[i] & 0xff).toString(16)).slice(-2);
    return s;
  } catch (e) { return "<err:" + e + ">"; }
}

Java.perform(function () {
  var hooked = [];

  // ---- HTTP (okhttp3): request completo + response de /publickey y /verify ----
  // Interceptamos en el punto donde se puede leer request Y response juntos:
  // okhttp3.Interceptor no siempre es accesible; usamos Request$Builder.build
  // para el request y ResponseBody.string para el response, correlacionando
  // por URL. Simple y robusto (ya probado en capture_gatt_unfiltered_v2.js).
  try {
    var RB = Java.use("okhttp3.Request$Builder");
    RB.build.overload().implementation = function () {
      var req = this.build();
      try {
        var url = String(req.url());
        if (url.indexOf("/publickey") !== -1 || url.indexOf("/verify") !== -1) {
          var tag = url.indexOf("/publickey") !== -1 ? "PUBKEY_REQ" : "VERIFY_REQ";
          var method = String(req.method());
          var hdrs = req.headers();
          var hlines = [];
          for (var i = 0; i < hdrs.size(); i++) {
            hlines.push(String(hdrs.name(i)) + ": " + String(hdrs.value(i)));
          }
          // body (RequestBody) -> volcar a un Buffer y leerlo
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
          L(tag + " " + method + " " + url);
          L(tag + "_HEADERS " + JSON.stringify(hlines));
          L(tag + "_BODY " + bodyStr);
        }
      } catch (_) {}
      return req;
    };
    hooked.push("okhttp.request");
  } catch (e) { console.log("PKFLOW_ERR request " + e); }

  try {
    var RespBody = Java.use("okhttp3.ResponseBody");
    RespBody.string.implementation = function () {
      var s = this.string();
      try {
        if (s && (s.indexOf("cloudPublicKey") !== -1 || s.indexOf("Public") !== -1 ||
                  s.indexOf("sessionKey") !== -1 || s.indexOf("verifyData") !== -1)) {
          // recorta a 1500 por si viene envuelto; suele ser corto
          L("HTTP_RESP " + s.slice(0, 1500));
        }
      } catch (_) {}
      return s;
    };
    hooked.push("okhttp.response");
  } catch (e) { console.log("PKFLOW_ERR response " + e); }

  // ---- GATT: escrituras ff07 (0610/0710) y notificaciones ff08 (crudas) ----
  var FF07 = "0000ff07";  // prefijo del UUID de auth WRITE
  var FF08 = "0000ff08";  // prefijo del UUID de auth NOTIFY
  try {
    var Gatt = Java.use("android.bluetooth.BluetoothGatt");
    Gatt.writeCharacteristic.overloads.forEach(function (ov) {
      ov.implementation = function () {
        try {
          var ch = arguments[0];
          var uuid = String(ch.getUuid());
          var val = ch.getValue();
          var hex = val ? jbytes2h(val) : "<null>";
          if (uuid.indexOf("ff07") !== -1) {
            L("FF07 uuid=" + uuid + " hex=" + hex);   // <-- fragmentos a reinyectar
          } else {
            L("WRITE_OTHER uuid=" + uuid + " hex=" + hex);
          }
        } catch (_) {}
        return ov.apply(this, arguments);
      };
    });
    hooked.push("writeCharacteristic");
  } catch (e) { console.log("PKFLOW_ERR write " + e); }

  try {
    var CB = Java.use("android.bluetooth.BluetoothGattCallback");
    CB.onCharacteristicChanged.overloads.forEach(function (ov) {
      ov.implementation = function () {
        try {
          var ch = arguments[1];
          var val = arguments.length > 2 ? arguments[2] : ch.getValue();
          var uuid = String(ch.getUuid());
          var hex = val ? jbytes2h(val) : "<null>";
          if (uuid.indexOf("ff08") !== -1) {
            L("FF08 uuid=" + uuid + " hex=" + hex);   // <-- respuesta del lock (control)
          } else {
            L("NOTIFY_OTHER uuid=" + uuid + " hex=" + hex);
          }
        } catch (_) {}
        return ov.apply(this, arguments);
      };
    });
    hooked.push("onCharacteristicChanged");
  } catch (e) { console.log("PKFLOW_ERR notify " + e); }

  console.log("PKFLOW_HOOKED " + JSON.stringify(hooked));
  console.log("PKFLOW_READY " + Date.now());
});
