// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 dani811 <https://github.com/dani811/Aqara>
//
// This file is part of Aqara BLE, licensed under the GNU Affero General Public
// License v3.0 (AGPL-3.0-only). You may use, study, share and modify it; any
// distributed or network-served derivative must stay licensed under the AGPL
// and keep this notice. See the LICENSE file for the full terms.

"use strict";
// Hook MINIMO: solo Request.Builder.build() + ResponseBody.string(), sin
// tocar Cipher/MessageDigest/LumiDevSDK. capture_login_flow.js (mas pesado,
// con reflexion sobre LumiDevSDK + overrides de Cipher/MessageDigest) crasheo
// SecNeo incluso en Frida 17.2.12 -- este es el experimento minimo para ver
// si el crash viene de esa parte pesada y no del hook de headers en si.
setInterval(function () {}, 5000);

function L(s) { console.log("HDRCAP ts=" + Date.now() + " " + s); }

Java.perform(function () {
  var hooked = [];
  try {
    var RB = Java.use("okhttp3.Request$Builder");
    RB.build.overload().implementation = function () {
      var req = this.build();
      try {
        var url = String(req.url());
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
        L("REQ " + String(req.method()) + " " + url);
        L("HEADERS " + JSON.stringify(hlines));
        L("BODY " + bodyStr);
      } catch (_) {}
      return req;
    };
    hooked.push("okhttp.request");
  } catch (e) { console.log("HDRCAP_ERR request " + e); }

  try {
    var RespBody = Java.use("okhttp3.ResponseBody");
    RespBody.string.implementation = function () {
      var s = this.string();
      try {
        if (s && s.length < 4000) L("RESP " + s.slice(0, 2000));
      } catch (_) {}
      return s;
    };
    hooked.push("okhttp.response");
  } catch (e) { console.log("HDRCAP_ERR response " + e); }

  console.log("HDRCAP_HOOKED " + JSON.stringify(hooked));
  console.log("HDRCAP_READY " + Date.now());
});
