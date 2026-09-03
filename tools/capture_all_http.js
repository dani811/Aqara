// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// Aqara BLE. Source-available under the PolyForm Noncommercial License 1.0.0.
// Noncommercial use only; any commercial or for-profit use requires a separate
// written license from the copyright holder. See the LICENSE file for the terms.

"use strict";
// ============================================================================
// CAPTURA HTTP COMPLETA — todas las llamadas okhttp3 de la app Aqara (sin filtro)
//
// A diferencia de capture_publickey_flow.js (que solo registra /publickey y
// /verify), este hook vuelca CADA request y CADA response que hace la app. Sirve
// para descubrir el endpoint de "listar dispositivos" (feature 016): con abrir la
// app, la ficha del lock y navegar un poco, sale la llamada del inventario, que
// contiene el device_id (matt.<...>), la MAC y el nombre — la request que hace
// falta para implementar list_devices() y quitar el device_id del config flow.
//
// USO:
//   1. adb -s <serie> forward tcp:27042 tcp:27042
//   2. cerrar app (force-stop), lanzar ESTE hook antes de reabrir:
//        python3 tools/run_hook.py tools/capture_all_http.js > /tmp/allhttp.log 2>&1 &
//      (si da "connection closed" en el 1er enganche, reintentar una vez)
//   3. abrir la app, entrar en la ficha del U200, moverse un poco.
//   4. cortar el hook. Buscar la llamada del inventario:
//        grep -iE "REQ .*(dev|device|position|home|family|query|list)" /tmp/allhttp.log
//        grep -iE "RESP .*(matt\.|lumi\.|deviceModel|positionName|\"did\")" /tmp/allhttp.log
//   Comparte SOLO esa request/response (redacta token/did/mac si quieres). Con
//   método + URL + body + headers puedo implementar list_devices() a la primera.
//
// Pantalla del móvil SIEMPRE encendida (la app pausa el BLE con pantalla apagada).
// ============================================================================
setInterval(function () {}, 5000);

function L(s) { console.log("ALLHTTP ts=" + Date.now() + " " + s); }

var _seq = 0;

Java.perform(function () {
  var hooked = [];

  // ---- REQUEST: okhttp3.Request$Builder.build() — método, URL, headers, body ----
  try {
    var RB = Java.use("okhttp3.Request$Builder");
    RB.build.overload().implementation = function () {
      var req = this.build();
      try {
        var url = String(req.url());
        var method = String(req.method());
        var n = ++_seq;
        var hdrs = req.headers();
        var hlines = [];
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
        L("REQ #" + n + " " + method + " " + url);
        L("REQ #" + n + " HEADERS " + JSON.stringify(hlines));
        L("REQ #" + n + " BODY " + bodyStr.slice(0, 4000));
      } catch (_) {}
      return req;
    };
    hooked.push("okhttp.request");
  } catch (e) { console.log("ALLHTTP_ERR request " + e); }

  // ---- RESPONSE: okhttp3.ResponseBody.string() — cuerpo completo (truncado) ----
  try {
    var RespBody = Java.use("okhttp3.ResponseBody");
    RespBody.string.implementation = function () {
      var s = this.string();
      try {
        if (s && s.length > 0) {
          L("RESP " + s.slice(0, 4000));
        }
      } catch (_) {}
      return s;
    };
    hooked.push("okhttp.response");
  } catch (e) { console.log("ALLHTTP_ERR response " + e); }

  console.log("ALLHTTP_HOOKED " + JSON.stringify(hooked));
  console.log("ALLHTTP_READY " + Date.now());
});
