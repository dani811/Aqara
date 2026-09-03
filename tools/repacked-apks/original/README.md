# Pristine official APK

Not tracked in git (binary, and it's Aqara's copyrighted APK — see repo
`.gitignore`). Pull it fresh from the phone before building any repacked
version, and re-pull if Aqara has pushed an app update since the last pull
(a repack against a stale original can behave differently from what's
actually installed and being tested against):

```bash
adb shell pm path com.lumiunited.aqarahome.play
# -> package:/data/app/~~<hash>/com.lumiunited.aqarahome.play-<hash>/base.apk
adb pull /data/app/~~<hash>/com.lumiunited.aqarahome.play-<hash>/base.apk \
  tools/repacked-apks/original/aqara-official.apk
```

`tools/repack_apk.sh` defaults to reading `aqara-official.apk` from this
folder.
