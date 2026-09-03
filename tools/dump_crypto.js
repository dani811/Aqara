'use strict';
// Native dump of liblumidevsdk / libaqara_ed crypto in/out (unfiltered, short bufs).
// The OTA data (ff91) is plaintext 0x11 XMODEM, so the crypto core is called ONLY
// for the encrypted CONTROL frames (ff61/ff62) — few calls, so we can dump them all
// and read what the app sends around the OTA start (the session-confirm handshake).
function toHexStr(ptr, len) {
  try { var a = new Uint8Array(Memory.readByteArray(ptr, len)); var s=''; for (var i=0;i<a.length;i++) s+=('0'+a[i].toString(16)).slice(-2); return s; } catch(e){ return '?'; }
}
function report(t,m){ send('MSG:['+t+'] '+m); }
var NAME_RE = /encrypt|decrypt|encode|decode|cipher|aes|ccm|content|getEncrypted|getDecrypted/i;
var LIBS = ['liblumidevsdk.so','libaqara_ed.so'];
function hookLib(lib){
  var mod; try { mod = Process.getModuleByName(lib); } catch(e){ return false; }
  report('module', lib+' @ '+mod.base);
  var syms=[]; try{ mod.enumerateExports().forEach(function(e){if(e.type==='function')syms.push(e);}); }catch(e){}
  try{ mod.enumerateSymbols().forEach(function(s){if(s.type==='function'&&s.address&&!s.address.isNull())syms.push(s);}); }catch(e){}
  var seen={}, n=0;
  syms.forEach(function(s){
    if(!s.name||!NAME_RE.test(s.name)) return;
    var k=s.address.toString(); if(seen[k])return; seen[k]=1;
    var name=lib+'!'+s.name;
    try { Interceptor.attach(s.address,{
      onEnter:function(args){ this.n=name; this.a=[args[0],args[1],args[2],args[3]];
        report('IN', name+' a0='+toHexStr(args[0],40)+' a1='+toHexStr(args[1],40)+' a2='+toHexStr(args[2],40)); },
      onLeave:function(ret){ report('OUT', this.n+' ret='+toHexStr(ret,40)); }
    }); n++; } catch(e){}
  });
  report('hook', lib+' hooked '+n);
  return true;
}
LIBS.forEach(hookLib);
// re-scan in case a lib loads later (BLE crypto lib on connect)
var tries=0; var iv=setInterval(function(){ tries++; LIBS.forEach(hookLib); if(tries>30) clearInterval(iv); },2000);
report('ready','dump_crypto loaded — start the language download now');
