# Aqara app — React Native device-plugin catalog

The Aqara app's per-device screens (the U200 lock's control UI included) are
**React Native plugins downloaded at runtime**, not bundled in the APK. This
was long suspected (see [[rn-bundle-enums]] memory,
[reverse-engineering.md](../reverse-engineering.md) §2) but never confirmed
end-to-end until 2026-08-30. This doc records the
mechanism and the full catalog as of that date, so a future session doesn't
have to re-discover it via Frida.

## The mechanism (no root, no Frida needed once you know this)

1. The app caches a **plain, unencrypted JSON** manifest at
   `files/lumi/reactnative/config/rn_bundle_config.json` inside its private
   app data (`/data/data/com.lumiunited.aqarahome.play/...`). Getting it off
   the device the first time needs a way to read app-private storage — the
   app is not debuggable (`run-as` fails), so a Frida gadget repack (native
   file I/O via `NativeFunction` bindings to `fopen`/`fread`, **not** Java
   hooks — see [reverse-engineering.md](../reverse-engineering.md) §2 for why)
   is the way in.
   `/sdcard` and `/data/local/tmp` are **not** writable from the app's own
   process (SELinux denies both even though the app can read/write its own
   `files/`/`cache/` dirs) — copy content out via `send()` over the Frida
   session instead of trying to stage a file for `adb pull`.
2. Each entry maps one or more **device models** (`lumi.*`/`aqara.*` model
   IDs, matching `AQARA_DEVICE_ID`-style identifiers) to a **plugin bundle**:
   a versioned `.zip` hosted on a **public CDN** (`cdn.aqara.com`, one entry
   uses an AWS S3 bucket instead). No auth header, no token — a plain `curl`
   downloads it.
3. Each zip contains `<bundleId>/<bundleId>.main.bundle` — **Hermes
   bytecode** (same format as the app's own shared `base.bundle`, see §2) —
   plus its per-locale drawables. Decompile with `hbc-decompiler` (works for
   Hermes v96; `hbctool` does not — see §2).

This means: **for any Aqara device, its actual control-screen source (byte
enums, opcode names, the real logic — not just i18n labels) is one `curl` +
one decompile away**, no live device or Frida needed for that model *if* you
already have a copy of `rn_bundle_config.json`. Getting that manifest still
needs one Frida session (or a rooted phone) — but only once; the CDN URLs
inside it are stable across sessions until Aqara ships a new plugin version
(the URL itself changes — it's a content hash — so **re-pull the manifest
occasionally** rather than assuming last time's URL is still current).

## U200 entry

```json
{
  "bundleId": "aqara.matter.4447_10242",
  "label": "门锁 U200 DA2",
  "models": ["lumi.lock.acn010", "aqara.matter.4447_10242"],
  "plugin": {
    "pluginVersion": "3.0.5",
    "url": "https://cdn.aqara.com/cdn/appadmin/mainland/rn/eddb8f69feea48368f8827bac13a37f9.zip"
  }
}
```

`lumi.lock.acn010` matches this project's `AQARA_DEVICE_ID` family. Decompiled
2026-08-30 (818k lines of recovered JS). Findings so far:

- Confirms the naming: `isSupportVoiceLanguageOta`, `voiceLanguageOtaList`,
  `mapLanguageValueToChannel`, `handleSetLanguageByChannel` — i.e. the
  language-change flow really is modeled as an OTA download keyed by a
  **channel string** (`chinese`/`english`/`russian`/`spanish`/`french`/
  `korean` per `ChannelLanguageType` in `Modules_common-lock_src_Constants_UserConstant.ts`),
  matching the live BLE capture (bulk file transfer on a separate
  unencrypted characteristic, see `docs/devices/u200/operations.md`).
- **Open discrepancy, not yet resolved:** `ChannelLanguageType` here lists
  only 6 channels (chinese/english/russian/spanish/french/korean) — it's
  missing German and Polish (both seen live in the U200's own app UI) and
  includes Korean (never seen in the U200's UI). Either this constant is
  shared/generic and the U200 uses a different or extended list at runtime
  (populated into `cloudLangList` from a **cloud API call**, not this static
  bundle), or there's a version mismatch between this decompile and the
  running app. Don't treat this list as authoritative for the U200 without
  re-verification.
- The exact **numeric byte** sent to the lock (e.g. the confirmed
  `code XOR 0x05` trailer scheme for English=2/Deutsch=9, see
  `docs/devices/u200/operations.md`) is **not visible in this JS** — it's
  built inside a native module (bridge call, not decompiled). Getting it
  statically would need ARM64 disassembly of the app's native `.so` — out of
  scope for this session.

## Full catalog (72 entries, 2026-08-30 snapshot)

Labels are the app's own Chinese-locale strings (the manifest doesn't carry
a per-locale label field — this is the source language). `models` is
comma-joined when a plugin covers several device IDs.

| bundleId | label | models | plugin version | url |
| --- | --- | --- | --- | --- |
| `app.group.thermostat_cooler` | 温控组 | app.group.thermostat_cooler, app.group.thermostat_heater, app.group.thermostat_radiator_new | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/ab729534c98c4269a7f5b2b9f9d967a7.zip |
| `aqara.bn.switch` | bn 开关 | lumi.models.4447_4146 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/7c4aa14101594ba5ba76345f183d1aba.zip |
| `aqara.gamut.light` | 淡彩全色域灯 | aqara.matter.4447_6182, aqara.matter.4447_6184, lumi.models.4447_6208, aqara.matter.4447_6179, lumi.models.4447_6182, aqara.matter.4447_6180, lumi.models.4447_6209, lumi.models.4447_6178, aqara.matter.4447_6185, lumi.models.4447_6213, aqara.matter.4447_6215, lumi.models.4447_6214, lumi.models.4447_6218, lumi.models.4447_6219 | 3.0.40 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/60d60185215a4172a1e4a5f6407928f6.zip |
| `aqara.lock.acn002` | 智能门锁S100 | aqara.lock.acn002 | 3.0.7 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/cc0be393655346e68f63059d3a5042fb.zip |
| `aqara.lock.acn005` | 门锁D200i | aqara.lock.acn005 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/df8da5a6036b4695aa255a4686a52a43.zip |
| `aqara.lock.acn008` | 智能门锁 N200 | aqara.lock.acn008 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/a262eeead5d84714b011dda6daaa7b0b.zip |
| `aqara.lock.acn10` | DA1 智能门锁U100 | aqara.lock.acn10 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/a1b7cacdd63f421684e276f93f7d968d.zip |
| `aqara.lock.agl002` | 智能门锁A100海外版 | aqara.lock.agl002 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/491b278fa9df46edaed0ecc9e515ef59.zip |
| `aqara.lock.aqgl01` | 智能门锁D100A | aqara.lock.aqgl01 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/552e7d447c234244999f8aea07c46bc4.zip |
| `aqara.lock.aus001` | DA1L 门锁U50 | aqara.lock.aus001 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/c5c9cfb68a5b4ee09e314ea4eee78ee1.zip |
| `aqara.lock.bzacn3` | N100(DL1A)业务包 | aqara.lock.bzacn4 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/2b725236412b4b7bb57c94a4c832064a.zip |
| `aqara.lock.dacn02` | DZ1&DZ1L 插件包 | aqara.lock.dacn03, aqara.lock.dacn02 | 3.0.7 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/e6a9a8b5fbc34bd0bbbbc548daa5e0dd.zip |
| `aqara.matter.4447_10241` | 门锁U300 DA3 | aqara.matter.4447_10241 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/3e821baf5cee4b25bca93b9a7b7a55c8.zip |
| **`aqara.matter.4447_10242`** | **门锁 U200 DA2** | **lumi.lock.acn010, aqara.matter.4447_10242** | **3.0.5** | **https://cdn.aqara.com/cdn/appadmin/mainland/rn/eddb8f69feea48368f8827bac13a37f9.zip** |
| `aqara.matter.4447_10245` | 门锁J200 DA2JP Set 套装版本 | aqara.matter.4447_10245 | 3.0.5 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1ee43cff365c43dbbfd96618395768bd.zip |
| `aqara.matter.4447_10247` | DA2L 门锁U200Lite | aqara.matter.4447_10247 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/359dd0a3029549f689503b39c3f0ddf8.zip |
| `aqara.matter.4447_10253` | 门锁 J200 DA2 JP 单主机版本 | aqara.matter.4447_10253 | 3.0.5 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/04dc1e9cd1bd4481b51d229bc09ba8c7.zip |
| `aqara.matter.4447_10254` | DO4 门锁 U500 | aqara.matter.4447_10256, aqara.matter.4447_10255, aqara.matter.4447_10254 | 3.0.8 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9c66ed5a81d64f46a964f8ceb676a4a0.zip |
| `aqara.matter.4447_10314` | 智能门锁 DA6UK U600 | aqara.matter.4447_10314 | 3.0.5 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/578369e5868b47ec93bba4ce083a53a2.zip |
| `aqara.matter.4447_16386` | 语音伴侣H1 | aqara.matter.4447_16386 | 3.0.5 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9b843d711a2247b89d75de932690f969.zip |
| `aqara.matter.4447_8201` | fp400传感器 标准版 | lumi.models.4447_8295, aqara.matter.4447_8201 | 3.0.27 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/bba0a8a789a043eab5b1ad226153fa3e.zip |
| `aqara.matter.devices` | matter 子设备通用包 | (none) | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/b89c1219280249e992671f17a450aa12.zip |
| `aqara.matter.light` | Matter 自研灯 | lumi.light.acn040, lumi.light.agl006, lumi.light.agl005, lumi.light.agl004, lumi.light.agl003, aqara.matter.4447_6147, aqara.matter.4447_6148, aqara.matter.4447_6149, aqara.matter.4447_6150 | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/3af27c5688424a0084a9d183feda7902.zip |
| `aqara.matter.rotary` | 欧标旋钮 | aqara.matter.4447_4102, lumi.switch.agl007, lumi.switch.agl011, aqara.matter.4447_4106 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/bf475d6164ef46e0a0d8a316964627b7.zip |
| `aqara.matter.switch` | Matter 自研开关 | aqara.matter.4447_4101, aqara.matter.4447_4100, aqara.matter.4447_4099, aqara.matter.4447_4104, aqara.matter.4447_4105 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/af34b1f5714a49fd8ea19dd8e5979189.zip |
| `aqara.module.log` | 日志插件 | (none) | 3.1.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/fa4d882573b24b899bf22ba7b975cea1.zip |
| `aqara.plugin.general.features` | 第三方服务授权 | (none) | 1.2.0 | https://aiot-common-ger.s3.eu-central-1.amazonaws.com/cdn/uplusadmin/mainland/rn/cc5d4a56eb4748b1b0b4933de635d12b.zip |
| `aqara.rn.base` | RN基础包 | (none) | 2.0.45 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1d5611fc1b7043b1b855d24dc6f277bd.zip |
| `aqara.sensor.devices` | 基础传感器通用插件 | aqara.matter.4447_8195, aqara.matter.4447_8194 | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/82042e6671d741689b8f49a6224a4a8e.zip |
| `aqara.spec.station` | 新物模型基站 | lumi.models.4447_2096 | 3.1.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/363ed6af7d84484b8177f225b37e0d80.zip |
| `aqara.switch.screen` | 美标带屏开关 S100 | aqara.matter.4447_4145 | 3.0.7 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/523330fc0166406085d5aec4b5774724.zip |
| `aqara.tape.light` | 屋檐灯串灯落地灯灯带 | lumi.models.4447_6174, aqara.matter.4447_6175, lumi.models.4447_6206, aqara.matter.4447_6177, lumi.models.4447_6176, lumi.models.4447_6207, aqara.matter.4447_6173, lumi.models.4447_6172, lumi.models.4447_6205, aqara.matter.4447_6183, lumi.models.4447_6212 | 3.0.105 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/d6737b1ce00248659b1468f60bffcdb8.zip |
| `aqara.thermostat.floor` | 地暖温控器 W500 | aqara.matter.4447_18435, lumi.airrtc.aeu001 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/3c524c94df974df883f266f90b215aa0.zip |
| `aqara.zigbee.switch` | Aqara zigbee 开关 | lumi.switch.agl010, lumi.switch.agl009, lumi.switch.agl006, lumi.switch.agl005, lumi.switch.agl004 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9c184ec0d2e74cc98e84806fe3ece6fd.zip |
| `lumi.airrtc.acn002` | 智能温控器S4 (氟机版) | lumi.airrtc.acn002 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/6728444c209240e99edee4a7a4275a83.zip |
| `lumi.airrtc.acn003` | 智能温控器S4 (水机版) | lumi.airrtc.acn003 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/d35c9b3c60f24207a1b772bd67bd1b56.zip |
| `lumi.airrtc.aeu005` | 智能阀式温控器W600 | lumi.airrtc.aeu005, aqara.matter.4447_18437 | 3.0.6 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/b242780c9563419f8a307221941fd8ce.zip |
| `lumi.airrtc.aus001` | 法拉盛 | lumi.airrtc.aus001, lumi.airrtc.aus002 | 3.2.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/6f225cb96ef842969e5112b18d4d6d1e.zip |
| `lumi.aoke.modules` | 奥科模组 | lumi.curtain.fngl02, lumi.curtain.fngl01, aqara.matter.5274_8229, aqara.matter.5274_8213, aqara.matter.4447_14338 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/f8b41709300c418e952aa9cf0ec3ccaa.zip |
| `lumi.curtain.acn010` | 窗帘电机 | lumi.curtain.acn010 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/d45caf3aa0bd46c2a21b11b393a6c8ab.zip |
| `lumi.fitting.agl001` | 互感器 | lumi.fitting.agl001 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/c227e26abfff4a5da76ab8bfcc6cd97a.zip |
| `lumi.gateway.acn012` | M3网关 | lumi.gateway.acn012, lumi.gateway.agl011, lumi.gateway.agl021 | 3.2.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/a071c286d3814a9a976bc6db6dfdb2a8.zip |
| `lumi.gateway.agl004` | M3 中枢网关(海外版) | lumi.gateway.agl004 | 3.2.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/840bfbebddb04377a5da61aad99134c6.zip |
| `lumi.gateway.agl008` | 网关 M100 海外版 | lumi.gateway.agl008 | 3.0.9 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1da56fb618fa48e4a8a6ffebc45f0583.zip |
| `lumi.gateway.agl012` | Hub M300 | lumi.gateway.agl012 | 3.0.9 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/c605bfc38b8944d185635552a3e4caf7.zip |
| `lumi.gateway.agl013` | 485网关 | lumi.gateway.agl013 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/ae88aaa5c49c44c1888d5172cd6d0397.zip |
| `lumi.gateway.agl014` | 网关 M410 | lumi.gateway.agl014 | 3.0.6 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/17be670e5344454eb63c433f61157c55.zip |
| `lumi.gateway.agl015` | 妙控场景屏 AX100S | lumi.gateway.agl015 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/c4e20c96353d454398ec9b218964d6d3.zip |
| `lumi.light.acn038` | 485灯箱 | lumi.light.acn038 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/680f1237c94441c9a3122abd81d58d03.zip |
| `lumi.light.acn041` | 万象天镜 | lumi.light.acn041 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/322185b72bec447ca427071fdb7122ef.zip |
| `lumi.lock.acn006` | 智能门 RD1 | lumi.lock.acn006 | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/c955890ccf7b483c8a26716a047e3a0c.zip |
| `lumi.lock.netAccess` | 门锁入网模块 | (none) | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9d1e4fbc5ecb4d26b10e01d791f80466.zip |
| `lumi.models.4447_14362` | 百叶帘调光伴侣C100 | lumi.models.4447_14362, aqara.matter.4447_14363 | 3.0.43 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/df094b0e7eae4ed5b4a69871ef206009.zip |
| `lumi.models.4447_8249` | 空间有无人软传感 | lumi.models.4447_8249 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1c7e4cf5e71f4a7cb623e80be9ae48a7.zip |
| `lumi.motion.ac01` | 体征探测器T1 | lumi.motion.ac01 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/ce1fb42e7db04e5881c909f0cf383309.zip |
| `lumi.plug.common` | Aqara 插座 | aqara.matter.4447_4110, lumi.plug.aeu002 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/f505330b275f4f60baf1b493628ac501.zip |
| `lumi.plug.move` | Aqara欧标移动插座 | aqara.matter.4447_4162, lumi.plug.aeu006, lumi.plug.aeu007, lumi.plug.aeu009, lumi.plug.aeu008, lumi.plug.aeu005, aqara.matter.4447_4160, aqara.matter.4447_4154, aqara.matter.4447_4152, lumi.plug.aeu004, aqara.matter.4447_4156, aqara.matter.4447_4158 | 3.0.2 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/b40a73f7756049048b31059fa07e3dbf.zip |
| `lumi.plugin.common` | 晾衣机和窗帘A1行程引导 | lumi.curtain.hagl08, lumi.curtain.acn002, lumi.airer.acn02, lumi.curtain.acn014 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/5908b2ae402c4e6e8045f73cefa6f2cf.zip |
| `lumi.remote.cagl02` | 魔方控制器 T1 Pro | lumi.remote.cagl02 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/647ece8cfdad48e1a89ba0a07c6569f5.zip |
| `lumi.sensor.fp3` | AI智能存在传感器 FP3 | lumi.sensor_occupy.agl8, aqara.matter.4447_8197, lumi.sensor_occupy.acn1, aqara.matter.4447_8206 | 3.0.7 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/35ac79c60e734848933533c33aa03ec6.zip |
| `lumi.sensor.p100` | 多功能传感器P100 | lumi.vibration.agl002, aqara.matter.4447_8203 | 3.0.21 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/042906b1ca884ce4a27d8be1c8558755.zip |
| `lumi.sensor_ht.agl001` | 温控伴侣 | aqara.matter.4447_8196, lumi.sensor_ht.agl001 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/139cd9c478fa42f3b81af1ab0c8013ff.zip |
| `lumi.sensor_occupy.agl9` | fp400 zigbee插件 | lumi.sensor_occupy.agl9 | 3.0.12 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/dabe3fbce33e4e94878e3083b5e89545.zip |
| `lumi.sensor_smoke.acn03` | 烟气感的设备自检 | lumi.sensor_gas.acn01, lumi.sensor_gas.acn02, lumi.sensor_smoke.acn03 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1d01b2375e9f4d21aa21b82c6f8298bc.zip |
| `lumi.switch.acn066` | 妙控场景屏 S100 | lumi.switch.acn066 | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9219ba508f714318bd845a9bd1e96f2c.zip |
| `lumi.switch.acn080` | 精英开关H2 | lumi.switch.acn080 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/9a32783b906b42b5a2c2e07bdd5de469.zip |
| `lumi.switch.aeu003` | 卷帘开关 | aqara.matter.4447_4109, lumi.switch.aeu003 | 3.0.5 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/db0ed1bb73154acdb22ee0547120f4de.zip |
| `lumi.switch.agl01` | 车库门 | lumi.switch.agl01 | 3.0.0 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/1f7e8d8ab2c84a04b94d1fd87c9238c1.zip |
| `lumi.switch.b1nc01` | 智能墙壁开关 E1 | lumi.switch.b2nc01, lumi.switch.b2lc04, lumi.switch.b1nc01, lumi.switch.b1lc04 | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/895addd736944596aa1ca960bfc2cc68.zip |
| `lumi.switch.legacy_upgrade` | 开关类老翻新项目 | lumi.switch.n3acn1, lumi.switch.n2acn1, lumi.switch.n1acn1, lumi.switch.l3acn1, lumi.switch.l2acn1, lumi.switch.l1acn1 | 3.0.4 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/ca99f9b1430c440d8c0a179c8c6c4864.zip |
| `matter.commission.core` | Matter直连入网插件 | (none) | 3.0.1 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/70a934194df64d58b71a0d393b9ce060.zip |
| `softsensor.temperature.humidity` | 温湿度软传感 | lumi.models.4447_8265, lumi.models.4447_8266 | 3.0.3 | https://cdn.aqara.com/cdn/appadmin/mainland/rn/562df4ca586242368b585993e732308a.zip |

## How to redo this in a future session

```bash
# 1. Repack the CURRENT official APK with a Frida gadget (see reverse-engineering.md §2
#    for the objection/zipalign/apksigner recipe — this is the only step needing the phone).
# 2. Cold-start the app, attach, and copy the manifest out over the Frida session
#    (send() the UTF-8-decoded content in ~3000-char chunks; /sdcard and
#    /data/local/tmp are NOT writable from the app's own process — this bit the
#    author twice before switching to send()).
python3 -c "
import frida, threading
device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
session = device.attach('Gadget')
chunks = []
done = threading.Event()
def on_message(message, data):
    p = message.get('payload')
    if p == '__DONE__': done.set()
    else: chunks.append(p)
script = session.create_script(open('read_config_clean.js').read())  # see below
script.on('message', on_message)
script.load()
done.wait(timeout=20)
open('rn_bundle_config.json', 'w', encoding='utf-8').write(''.join(chunks))
"
# 3. curl any bundleId's plugin.url, unzip, hbc-decompiler the .main.bundle.
```

The `read_config_clean.js` Frida script (native `fopen`/`fread` + manual UTF-8
decode, no Java/ART touched) lived in the session scratchpad, not the repo —
rewrite it from this doc's description if needed (it's ~40 lines, see the
"native (libc) file read, chunked `send()`" pattern above).
