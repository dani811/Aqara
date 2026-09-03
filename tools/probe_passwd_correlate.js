// Correlate getSignHead (the signed body) with the real HTTP request
// (method + :path + wire body), to learn EXACTLY how the offline-password
// /dev/bluetooth/lock/passwd fetch is built. Native-only (safe under SecNeo).
//
// Correlation key = the Sign value: getSignHead RETURNS it for a given body,
// and the HTTP request carries it as the `sign` header. Match the sign string
// across the two logs → (signed body) ↔ (method, path, wire body).
//
// Writes two files in the app's files/cap/ dir:
//   sign.log  lines: SIGN <sign> BODY <signed-body>
//   https.log full-hex SSL_write/read (decode with tools/decode_h2.py)
//
// Attach: python3 tools/frida_attach.py tools/probe_passwd_correlate.js --seconds 150
// Then in the app: open "Contraseña sin conexión" and tap "Crear".
'use strict';

var DIR = '/sdcard/Android/data/com.lumiunited.aqarahome.play/files/cap';
function mkfile(name){ try { return new File(DIR + '/' + name, 'ab'); } catch(e){ try { return new File('/data/local/tmp/'+name,'ab'); } catch(e2){ return null; } } }
var fSign = mkfile('sign.log');
var fHttp = mkfile('https.log');
function wSign(s){ if(fSign){ try{ fSign.write(s+'\n'); fSign.flush(); }catch(e){} } }
function wHttp(s){ if(fHttp){ try{ fHttp.write(s+'\n'); fHttp.flush(); }catch(e){} } }
function toHex(b){ var a=new Uint8Array(b),o=new Array(a.length); for(var i=0;i<a.length;i++)o[i]=('0'+a[i].toString(16)).slice(-2); return o.join(''); }

setTimeout(function () {
  // getSignHead: read arg6 (body) + return (sign) as JNI strings
  try {
    var addr = Process.getModuleByName('liblumidevsdk.so').findExportByName('Java_com_lumi_lumidevsdk_LumiDevSDK_getSignHead');
    function j(env, x){ if(x.isNull())return null; try{ var t=env.readPointer(); var g=t.add(169*Process.pointerSize).readPointer(); var f=new NativeFunction(g,'pointer',['pointer','pointer','pointer']); var c=f(env,x,ptr(0)); return c.isNull()?null:c.readUtf8String(); }catch(e){return null;} }
    Interceptor.attach(addr, {
      onEnter: function(a){ this.env=a[0]; this.body=j(a[0],a[6]); },
      onLeave: function(r){ var sign=j(this.env,r); wSign('SIGN '+sign+' BODY '+JSON.stringify(this.body)); }
    });
    send('getSignHead hooked');
  } catch(e){ send('ERR signhead '+e); }

  // SSL full hex across the OkHttp stack
  var hooked={};
  function hookSSL(m){
    if(hooked[m.name])return; var rp,wp;
    try{rp=m.findExportByName('SSL_read');}catch(e){rp=null;}
    try{wp=m.findExportByName('SSL_write');}catch(e){wp=null;}
    if(!rp&&!wp)return; hooked[m.name]=true;
    if(rp)try{Interceptor.attach(rp,{onEnter:function(a){this.ssl=a[0];this.buf=a[1];},onLeave:function(rv){var n=rv.toInt32();if(n>0){try{wHttp('==== '+Date.now()+' SSL_read ['+m.name+'] ssl='+this.ssl+' len='+n+' ====');wHttp(toHex(this.buf.readByteArray(n)));}catch(e){}}}});}catch(e){}
    if(wp)try{Interceptor.attach(wp,{onEnter:function(a){var n=a[2].toInt32();if(n>0){try{wHttp('==== '+Date.now()+' SSL_write ['+m.name+'] ssl='+a[0]+' len='+n+' ====');wHttp(toHex(a[1].readByteArray(n)));}catch(e){}}}});}catch(e){}
  }
  Process.enumerateModules().forEach(hookSSL);
  send('SSL hooked: '+Object.keys(hooked).join(','));
}, 0);
