# U200 — operations catalog

**Layer:** device-specific (U200)

> Reverse-engineered by decrypting the AES-CCM control channel with the real
> session key and correlating each frame with an app action, plus the enum
> extracted from the app. Payloads are protocol opcodes, not secrets
> (Constitution Principles I & IV).

The [control channel](../../reference/control-channel.md) is transversal; the set
of **commands** it carries is device-specific. This is the U200's set.

## Confirmed operations

Captured live from the app's encryption input and replayed successfully on the
reference lock.

| Operation | Payload (hex) | Write prefix | Notes |
|-----------|---------------|--------------|-------|
| `UNLOCK` (open) | `74010100b917` | `0x01` | `0x74` = BLE_OPEN_LOCK, byte 1 `0x01` = open |
| `LOCK` (close) | `740002003a12` | `0x01` | byte 1 `0x00` = close |
| `KEEPALIVE` | `2f012f` | `0x01` | `0x2f` = HEART_PCK; status poll |
| `SET_VERIFY_FAIL_TIME` | `af780000000c4a` | `0x01` | `0xaf`; `af <seconds:4 LE> <trailer:2>`. 0x78=120s (2 min). `build_set_verify_fail_time()` |
| `SET_AUTO_LOCKUP_DELAY_TIME` (re-lock timer) | `d50a000efe` | `0x01` | `0xd5`; `d5 <seconds:2 LE> <kind=0x0e> <trailer=0xfe>`. 0x0a=10s. **Same opcode also covers the OTHER auto-lock timer** (kind=0x01, see next row) — there is no separate 0xAD frame. `build_set_auto_lockup_delay_time()` |
| `SET_AUTO_LOCKUP_DELAY_TIME` (on-close timer) | `d50500 01fe` | `0x01` | same opcode, `kind=0x01`="Bloqueo automático al cerrar" timer. 5s confirmed. `build_set_auto_lock_on_close_delay_time()` |
| `LANGUAGE` | `03028307` | `0x01` | `0x03`; `03 <code> 83 <code XOR 0x05>`. `code=0x02`=English, `code=0x09`=Deutsch, both ACK'd live. `build_set_language_english()` / `build_set_language_deutsch()` — see §2026-08-30 for the corrected byte-position and the Español blocker. |
| `SET_AUXILIARY_LOCKING` (on-close enable) | `c402000698` | `0x01` | `0xc4`; `c4 <kind> <val:2> <trailer=0x98>`. `kind=0x02`="Bloqueo automático al cerrar" ON. `build_set_auxiliary_locking_on_close_enabled()` |
| `SET_AUXILIARY_LOCKING` (re-lock enable) | `c404000098` | `0x01` | same opcode, `kind=0x04`="Re-bloqueo de seguridad" ON. `build_set_auxiliary_locking_relock_enabled()` |
| `SET_DOORLOCK_ALARM_VOLUME` | `83021007` | `0x01` | `0x83`; `83 02 <val> 07`. `val=0x10`=Normal, `val=0x00`=Silencio (only 2 levels). `build_set_alarm_volume()` |
| `SET_ALERT_VOLUME` | `020203040f` | `0x01` | `0x02` kind=`0x02`; `02 02 <val> 04 <val+0x0c>`. 4-level "Volumen de alerta" enum (01=Alto/02=Medio/03=Bajo/04=Silencio), distinct from voice volume (same opcode, kind=`0x04`) and alarm volume (`0x83`). `build_set_alert_volume()` |
| `SET_ALERT_DELAY` | `18050a033c88e3` | `0x01` | `0x18`; `18 05 0a 03 <seconds> 88 <seconds XOR 0xdf>`. "Retraso de alerta". The app's own decompiled source calls sub-cmd `0x18` "UN_LOCK" — a genuine, unresolved contradiction with this live capture, not a stale/guessed label; see [u200-app-opcode-table.md](u200-app-opcode-table.md#-one-important-contradiction-not-swept-under-the-rug). Trust the live capture for what `0x18` actually does. `build_set_alert_delay()` |

The confirmed frames start with their **sub-command** byte (`74…`, `2f…`) — the
family/mainCmd is an app-side grouping, not a wire prefix.

### Operate-frame builder

The actuation frame is `74 <dir:1> <seq:2 LE> <trailer:2 LE>`:

- `dir` = `01` open / `00` close.
- `trailer` is **additive** (not a CRC): `trailer = base_dir + seq`, with
  `base_open = 0x17b8`, `base_close = 0x1238`. Cracked from nine live captures
  (the trailer increments by 1 with the sequence).
- `UNLOCK`/`LOCK` are the `seq = 1` case. The lock ignores the sequence across
  sessions, so `seq = 1` per fresh session is fine.

> The bases were derived from **one** device and may be device-specific — re-derive
> them from captures on a new device.

Each operation is sent encrypted:
`control_write = write_prefix + AES-CCM(sessionKey, nonce, payload)`.

> **Read protocol:** how these opcodes are *read* (the `<opcode> <kind> <body>`
> frame, and the ff61 write-prefix — `01` for most, `03` for finger `0x20`/log-sync
> `0x13`/`0x1f`/voice-OTA `0xa6`) is in
> [settings-protocol.md](settings-protocol.md). **All settings read over BLE from
> our own session** — volume, language, alarm-volume, finger and lock-setting were
> confirmed live 6/6 (2026-08-27). The earlier "privilege-gated / app-only" claim
> was two client bugs, now fixed; see settings-protocol.md and specs 036/037
> (RESOLVED).

### Voice / alert volume

| Preset | Serialized request (hex) — `kind|command|body|trailer` |
|--------|--------------------------------------------------------|
| `MEDIUM` | `01 d3 02d13e15 d5fddfe4` |
| `HIGH` | `01 d3 02d23e16 5faddd09` |

## Full catalog (from the app enum)

234 operations across 8 families; `confirmed` = verified live, `catalogued` = from
the enum with exact `data` unverified. The two confirmed above are `0x74`
(BLE_OPEN_LOCK) and `0x2f` (HEART_PCK); everything else is `catalogued`. The
SYSTEM family's naming was cross-checked 2026-08-30 against the app's own
decompiled source (not just an extracted enum) — see
[u200-app-opcode-table.md](u200-app-opcode-table.md) for the full 151-entry
table, the diff against this catalog, and the one unresolved naming
contradiction (`0x18`). 20 SYSTEM opcodes present in that source table but
missing from this catalog were added as `catalogued` (name-only, no frame)
on 2026-08-30: `0x1d/0x1e/0x34/0x35/0x36/0x37/0x3c/0x41/0x42/0x44/0x45/0x46/
0x47/0x63/0x64/0xdc/0xdd/0xea/0xef/0xf1`.

### SYSTEM (`0x01`, reply `0x81`)

| sub | name | status |
|-----|------|--------|
| `0x01` | SYSTEM_TIME | catalogued |
| `0x02` | VOLUME | confirmed (voice `02 04 <lvl>` AND alert `02 02 <val> 04 <val+0x0c>`, kind byte disambiguates) |
| `0x03` | LANGUAGE | confirmed (English only, see §Full catalog byte notes) |
| `0x04` | DOUBLE_VERIFY | catalogued |
| `0x07` | LOCK_STATUS | catalogued |
| `0x08` | TONGUE_STATUS | catalogued |
| `0x09` | REPORT_TONGUE_STATUS | catalogued |
| `0x0a` | REPORT_BATTERY | catalogued |
| `0x0b` | REPORT_VOLUME | catalogued |
| `0x0c` | REPORT_LANGUAGE | catalogued |
| `0x0d` | FIRMWARE_VERSION | catalogued |
| `0x11` | REPORT_WIFI_STATUS | catalogued |
| `0x14` | LOCAL_SETTING | catalogued |
| `0x15` | REPORT_LOCK_STATUS | catalogued |
| `0x16` | TEMP_PWD | catalogued |
| `0x17` | REPORT_TEMP_PWD | catalogued |
| `0x18` | UN_LOCK | confirmed live as SET_ALERT_DELAY, not unlock — the app's own decompiled source really does call it "UN_LOCK", an unresolved naming contradiction, see [u200-app-opcode-table.md](u200-app-opcode-table.md#-one-important-contradiction-not-swept-under-the-rug) |
| `0x1a` | LOCK_SETTING | catalogued |
| `0x1b` | REPORT_UN_LOCK | catalogued |
| `0x1c` | DEL_TEMP_PWD | catalogued |
| `0x1d` | REPORT_LOCK_LOG | catalogued |
| `0x1e` | REPORT_DOOR_LOG | catalogued |
| `0x20` | FINGER_COUNT | catalogued |
| `0x21` | HARDWARE_VERSION | catalogued |
| `0x22` | BIND_NFC_FLAG | catalogued |
| `0x23` | NFC_APDU | catalogued |
| `0x24` | APDU | catalogued |
| `0x25` | OTA_UPGRADE | catalogued |
| `0x26` | FINGER_KEY | catalogued |
| `0x27` | TONGUE_ENABLE | catalogued |
| `0x28` | FINGERPRINT_ALGORITHM_PARAMS | catalogued |
| `0x29` | LOCK_WORKING_MODE | catalogued |
| `0x2a` | KEY_IN_STATUS | catalogued |
| `0x2b` | REPORT_KEY_STATUS | catalogued |
| `0x2c` | BLE_CONNECT | catalogued |
| `0x2d` | REPORT_MUTE | catalogued |
| `0x2e` | SE_APDU | catalogued |
| `0x2f` | HEART_PCK | ✅ confirmed |
| `0x30` | HANDLE_DIRECTION | catalogued |
| `0x33` | TIMEZONE_TIME | catalogued |
| `0x34` | SET_SAFE | catalogued |
| `0x35` | READ_SAFE | catalogued |
| `0x36` | READ_HOME_AWAY | catalogued |
| `0x37` | REPORT_HOME_AWAY | catalogued |
| `0x39` | READ_AWAY_HOME_STATUS | catalogued |
| `0x3a` | HOMEKIT_BIND | catalogued |
| `0x3b` | HOMEKIT_BROADCAST | catalogued |
| `0x3c` | SET_ELECTORNIC_LOCK | catalogued |
| `0x3f` | CONFIG_ZIGBEE | catalogued |
| `0x41` | SET_INFRARD_VISION | catalogued |
| `0x42` | READ_INFRARD_VISION | catalogued |
| `0x44` | SET_STAY_DETECTION | catalogued |
| `0x45` | READ_STAY_DETECTION | catalogued |
| `0x46` | SET_VIDIO_RECORD_TIME | catalogued |
| `0x47` | READ_VIDIO_RECORD_TIME | catalogued |
| `0x48` | SET_DOOR_BELL | catalogued |
| `0x49` | READ_DOOR_BELL | catalogued |
| `0x4a` | ZIGBEE_STATUS | catalogued |
| `0x4b` | SET_TEMP_OPEN | catalogued |
| `0x4c` | READ_TEMP_OPEN | catalogued |
| `0x4d` | DEVICE_MTU | catalogued |
| `0x4f` | BATTERY | catalogued |
| `0x50` | REPORT_BATTERY_POWER | catalogued |
| `0x5b` | WIRELESS_OTA_STATUS | catalogued |
| `0x5c` | SET_OTA_SWITCH_TIME | catalogued |
| `0x5d` | GET_OTA_SWITCH_TIME | catalogued |
| `0x61` | REPORT_ZIGBEE_STATUS | catalogued |
| `0x63` | PICTURE_QUALITY_PARAMS | catalogued |
| `0x64` | READ_PICTURE_QUALITY_PARAMS | catalogued |
| `0x68` | READ_LOCK_LANGUAGE | catalogued |
| `0x70` | SET_DOOR_BELL_PUSH_SWITCH | catalogued |
| `0x71` | READ_DOOR_BELL_PUSH_SWITCH | catalogued |
| `0x74` | BLE_OPEN_LOCK | ✅ confirmed |
| `0x77` | REPORT_LITHIUM_BATTERY_STATUS | catalogued |
| `0x78` | GET_LITHIUM_BATTERY_STATUS | catalogued |
| `0x7a` | SET_ULTRASONIC_DISTANCE | catalogued |
| `0x7b` | GET_ULTRASONIC_DISTANCE | catalogued |
| `0x7c` | SET_DISABLE_FACE_RECOGNITION_TIME | catalogued |
| `0x7d` | GET_DISABLE_FACE_RECOGNITION_TIME | catalogued |
| `0x83` | SET_DOORLOCK_ALARM_VOLUME | catalogued |
| `0x84` | QUERY_DOORLOCK_ALARM_VOLUME | catalogued |
| `0x8b` | SET_MOTOR_AUTO_LOCK_AND_RELEASE_TIME | catalogued |
| `0x8c` | QUERY_MOTOR_AUTO_LOCK_AND_RELEASE_TIME | catalogued |
| `0x8d` | SET_MOTOR_DIRECTION_AND_TORQUE | catalogued |
| `0x8e` | QUERY_MOTOR_DIRECTION_AND_TORQUE | catalogued |
| `0x8f` | QUERY_WIFI_STATUS | catalogued |
| `0x93` | SET_AWAY_HOME_STATUS | catalogued |
| `0x94` | REPORT_AWAY_HOME_STATUS | catalogued |
| `0xa2` | QUERY_WIFI_CONFIG_STATUS | catalogued |
| `0xa3` | SET_NO_DISTURB_MODE | catalogued |
| `0xa4` | QUERY_NO_DISTURB_MODE | catalogued |
| `0xa7` | DOWNGRADE_PROTECTION | catalogued |
| `0xaa` | SET_FACE_IDENTIFY_ON_OFF | catalogued |
| `0xab` | GET_FACE_IDENTIFY_ON_OFF | catalogued |
| `0xad` | SET_AUTO_LOCK_TIME | catalogued (both auto-lock timers turned out to live on `0xd5`, see §Full catalog byte notes — an earlier 0xad sample was unrelated noise) |
| `0xae` | GET_AUTO_LOCK_TIME | catalogued |
| `0xaf` | SET_VERIFY_FAIL_TIME | ✅ confirmed |
| `0xb0` | GET_VERIFY_FAIL_TIME | catalogued |
| `0xb5` | SET_OTHER_PLATFORM | catalogued |
| `0xb6` | GET_OTHER_PLATFORM | catalogued |
| `0xbb` | REPORT_MOTOR_SETTING | catalogued |
| `0xbf` | SET_OPEN_DOOR_DIRECTION | catalogued |
| `0xc0` | GET_OPEN_DOOR_DIRECTION | catalogued |
| `0xc3` | GET_LOCK_VOLUME | catalogued |
| `0xc4` | SET_AUXILIARY_LOCKING | ✅ confirmed (ON frames for both sub-toggles; no OFF frame yet) |
| `0xc5` | GET_AUXILIARY_LOCKING | catalogued |
| `0xc6` | SET_NORMALLY_OPEN_MODE | catalogued |
| `0xc7` | GET_NORMALLY_OPEN_MODE | catalogued |
| `0xc8` | SET_NORMALLY_OPEN_MODE_PWD | catalogued |
| `0xc9` | SET_LOCK_CALIBRATION | catalogued |
| `0xca` | SET_ALARM_ENABLE | catalogued |
| `0xcb` | GET_ALARM_ENABLE | catalogued |
| `0xcc` | ANTI_LOCK_MANAGER_STATUS | catalogued |
| `0xcd` | REPORT_ANTI_LOCK_MANAGER_STATUS | catalogued |
| `0xd5` | SET_AUTO_LOCKUP_DELAY_TIME | ✅ confirmed |
| `0xd6` | GET_AUTO_LOCKUP_DELAY_TIME | catalogued |
| `0xd7` | SET_ADVANCED_MODE | catalogued |
| `0xd8` | GET_ADVANCED_MODE | catalogued |
| `0xd9` | UWB_CONFIG | catalogued |
| `0xda` | UWB_REPORT | catalogued |
| `0xdb` | UWB_DISTANCE | catalogued |
| `0xdc` | GET_REPORT_NORMALLY_OPEN_MODE_STATE | catalogued |
| `0xdd` | GET_FRONT_CONNECTION | catalogued |
| `0xde` | GET_BATTERY_INFO | catalogued |
| `0xdf` | SET_DOOR_LOCK_TYPE | catalogued |
| `0xe0` | GET_DOOR_LOCK_TYPE | catalogued |
| `0xe1` | SET_LIMIT_POINT | catalogued |
| `0xe2` | GET_LIMIT_INFO | catalogued |
| `0xe3` | SET_PULL_SPRING | catalogued |
| `0xe4` | GET_PULL_SPRING | catalogued |
| `0xe5` | GET_DOOR_LOCK_STATUS | catalogued |
| `0xe6` | REPORT_DOOR_LOCK_STATUS | catalogued |
| `0xe8` | SET_ASSIST_TURN | catalogued |
| `0xe9` | GET_ASSIST_TURN | catalogued |
| `0xea` | SET_AND_REPORT_VOICE_OTA_STATUS | catalogued |
| `0xeb` | SET_SILENT_CONTROL_LOCK | confirmed (partial, see §Full catalog byte notes) |
| `0xec` | GET_SILENT_CONTROL_LOCK | catalogued |
| `0xed` | SET_LOCK_WORK_MODE | catalogued |
| `0xee` | GET_LOCK_WORK_MODE | catalogued |
| `0xef` | SET_PASSAGE_DATA | catalogued |
| `0xf1` | GET_PASSAGE_DATA | catalogued |
| `0xf2` | SET_GOOGLE_VOICE_UNLOCK_STATE | catalogued |
| `0xf3` | GET_GOOGLE_VOICE_UNLOCK_STATE | catalogued |
| `0xf4` | REPORT_E2E_SECRET_KEY | catalogued |
| `0xf9` | SET_UWB_ANTI_ATTACK | catalogued |
| `0xfa` | GET_UWB_ANTI_ATTACK | catalogued |
| `0xfb` | SET_ASSIST_TURN_ENABLE | catalogued |
| `0xfc` | GET_ASSIST_TURN_ENABLE | catalogued |
| `0xfd` | SET_UWB_APPROACH_DIRECTION | catalogued |
| `0xfe` | GET_UWB_APPROACH_DIRECTION | catalogued |

### USER (`0x02`, reply `0x82`)

| sub | name | status |
|-----|------|--------|
| `0x01` | ADD_USER | catalogued |
| `0x02` | QUIT_ADD_USER | catalogued |
| `0x03` | DEL_USER | catalogued |
| `0x05` | DEL_USER_GROUP | catalogued |
| `0x06` | REPORT_USER_ID | catalogued |
| `0x07` | FINGER_REGISTER | catalogued |
| `0x08` | SET_USER_GROUP_PERMISSION | catalogued |
| `0x09` | REPORT_USER_GROUP_PERMISSION | catalogued |
| `0x0a` | MODIFY_USER_GROUP_ID_PERMISSION | catalogued |
| `0x0b` | REPORT_USER_GROUP_ID_PERMISSION | catalogued |
| `0x0c` | REPORT_ADD_USER_TIMEOUT | catalogued |
| `0x0d` | NFC_CID | catalogued |
| `0x0e` | USER_EFFECTIVE_PERIOD | catalogued |
| `0x0f` | REPORT_USER_VERIFY_VALID | catalogued |
| `0x10` | MODIFY_PWD | catalogued |
| `0x11` | ADD_SUCCESS | catalogued |
| `0x13` | ADD_VISITOR_PWD | catalogued |
| `0x14` | ABORT_ADD_MIOT_USER | catalogued |
| `0x15` | REPORT_USER_ID_NEW | catalogued |
| `0x18` | QUERY_ENABLE_GROUP_ID | catalogued |
| `0x1a` | GET_USER_NAME_SYNC_STATUS | catalogued |
| `0x20` | ADD_VISITOR_AND_SET_VISITOR_PWD_VALID_TIME | catalogued |

### LOG (`0x03`, reply `0x83`)

| sub | name | status |
|-----|------|--------|
| `0x01` | SYNC_USER_ID | catalogued |
| `0x08` | READ_TEMP_PWD | catalogued |
| `0x0a` | READ_DEVICE_INFO | catalogued |
| `0x0b` | NFC_CPLC | catalogued |
| `0x11` | SE_APDU | catalogued |
| `0x12` | SYNC_DOOR_LOCK_LOG | catalogued |
| `0x13` | SYNC_LOG | catalogued |
| `0x14` | SYNC_USER_ID_VALID_PERIOD | catalogued |
| `0x17` | WIFI_SCAN_AP | catalogued |
| `0x18` | WIFI_STATUS_QUERY | catalogued |
| `0x19` | ZIGBEE_INSTALL_CODE | catalogued |
| `0x1a` | SYNC_OTA_URL | catalogued |
| `0x1f` | SYNC_MIOT_USER_ID_VALID | catalogued |
| `0x20` | SYNC_MIOT_CREDENTIAL_PERIOD | catalogued |
| `0x21` | SET_VISITOR_PWD_VALID_TIME | catalogued |
| `0x24` | GET_MORE_CREDENTIAL_INFO | catalogued |
| `0x27` | SET_USER_NAME_AND_CREDENTIAL_NAME | catalogued |
| `0x3e` | SET_WIFI_AP_INFO | catalogued |
| `0x75` | WIFI_ENABLE | catalogued |
| `0x76` | WIFI_SETTING | catalogued |
| `0xa5` | VOICE_OTA_INFO_SET | catalogued |
| `0xa6` | VOICE_OTA_INFO_GET | catalogued |

### ALARM (`0x04`, reply `0x84`)

| sub | name | status |
|-----|------|--------|
| `0x01` | ALARM | catalogued |
| `0x02` | REMOVE_ALARM | catalogued |

### DEVICELOG (`0x05`, reply `0x85`)

| sub | name | status |
|-----|------|--------|
| `0x01` | SET_SWITCH | catalogued |
| `0x02` | GET_SWITCH | catalogued |
| `0x03` | SYNC_DEVICE_LOG | catalogued |
| `0x04` | STOP_SYNC | catalogued |

### XXQ (`0x06`, reply `0x86`)

| sub | name | status |
|-----|------|--------|
| `0x01` | SET_VOICE_AWAKE_ACTION | catalogued |
| `0x02` | READ_VOICE_AWAKE_ACTION | catalogued |
| `0x03` | SET_INDICATOR_LIGHT | catalogued |
| `0x04` | READ_INDICATOR_LIGHT | catalogued |
| `0x05` | SET_SENSOR_MODE | catalogued |
| `0x06` | READ_SENSOR_MODE | catalogued |
| `0x07` | SET_SILENT_EXECUTION | catalogued |
| `0x08` | READ_SILENT_EXECUTION | catalogued |
| `0x09` | SET_VOICE_RECOGNITION | catalogued |
| `0x0a` | READ_VOICE_RECOGNITION | catalogued |
| `0x0b` | SET_GATEWAY_ADDRESS | catalogued |
| `0x0c` | READ_GATEWAY_ADDRESS | catalogued |
| `0x0d` | SET_ROAMING_SWITCH | catalogued |
| `0x0e` | READ_ROAMING_SWITCH | catalogued |
| `0x0f` | SET_DIAGNOSE_SWITCH | catalogued |
| `0xde` | READ_BATTERY_INFO | catalogued |

### SYSTEM_EXT (`0x07`, reply `0x87`)

| sub | name | status |
|-----|------|--------|
| `0x01` | GET_MATTER_PAIRING_CODE | catalogued |
| `0x02` | GET_MATTER_LIST | catalogued |
| `0x03` | REMOVE_MATTER_INFO | catalogued |
| `0x04` | OPERATE_DEVICE | catalogued |
| `0x05` | SET_TRAFFIC_CARD_ENABLE | catalogued |
| `0x06` | GET_TRAFFIC_CARD_ENABLE | catalogued |
| `0x07` | ASSOCIATE_LOCK | catalogued |
| `0x08` | REPORT_ASSOCIATION_EVENT | catalogued |
| `0x0b` | SET_AUTO_LOCK_TIME_EXT | catalogued |
| `0x0c` | GET_AUTO_LOCK_TIME_EXT | catalogued |
| `0x0d` | SET_MECHANICAL_UNLOCK_LINKAGE | catalogued |
| `0x0e` | GET_MECHANICAL_UNLOCK_LINKAGE | catalogued |
| `0x0f` | SET_FACE_RECOGNITION_PARAMS | catalogued |
| `0x10` | GET_FACE_RECOGNITION_PARAMS | catalogued |
| `0x11` | INDOOR_KEY_LOCK_DELAY_TIME | catalogued |
| `0x25` | SET_LOCK_ASSOCIATION_INFO | catalogued |
| `0x26` | GET_LOCK_ASSOCIATION_INFO | catalogued |

### LONG (`0x3f`, reply `0xbf`)

| sub | name | status |
|-----|------|--------|
| `0x00` | LONG_PACKAGE | catalogued |

## Promoting a catalogued command to confirmed

To recover a command's exact `data` and mark it confirmed:

1. **Capture live** — instrument the app, perform the operation once, and read the
   plaintext `sub_cmd + data` from the control-channel encryption input.
2. **Or read the app's own command builder** for the `data` structure.

Then record the confirmed frame and update the command's status.


## Observed control responses (feature 019)

The decrypted control response of a command carries state. Confirmed samples
(2026-08-17, own lock/account):

| Command sent | Decrypted response |
| --- | --- |
| `keepalive` (`2f012f`) | `2f00 2c06` |
| `unlock` (open) | `7400 7706` |
| `battery` (`de00 158b3609`) | `de00 07000101 30 0000 c70a` → **48 %** |

`aqara_ble.LockState` exposes the raw response; decoded fields
(`locked`, `battery_percent`) stay `None` until a **labelled** sample set pins
them down. **Decode is pending** — capture procedure in
[validation.md](validation.md). Spontaneous event reports (manual unlock, keypad)
are a **known limit**: they need a persistent session/subscription (a future
feature), not the on-demand poll this feature adds.


## Status-query probing (feature 021)

The keepalive/operate/state_snapshot responses are **static** (verified live —
none change with bolt position). To find the byte that reports position, probe the
catalogued **status/battery** opcodes read-only via `aqara query <name>` or
`U200Client.query(opcode)`:

| CLI name | opcode | catalog |
| --- | --- | --- |
| `lock_status` | `0x07` | LOCK_STATUS |
| `tongue_status` | `0x08` | TONGUE_STATUS |
| `door_lock_status` | `0xE5` | GET_DOOR_LOCK_STATUS |
| `report_lock_status` | `0x15` | REPORT_LOCK_STATUS |
| `battery` | `0x4F` | BATTERY |
| `lithium_battery` | `0x78` | GET_LITHIUM_BATTERY_STATUS |

These are **unconfirmed** probes (the payload is guessed as the bare opcode). The
CLI only exposes these read-only names — `SET_*` opcodes are never sendable from
`aqara query`. Run each in a known physical state (locked vs unlocked) and compare
the `raw=`; whichever differs carries the position and feeds `LockState` decoding.

## Reading status/battery — the frame shape that works (feature 030)

The feature-021 probes above got **no response** because they sent only the bare
opcode byte. The lock ignores that. A **read** must have the full control-frame
shape (see [control-channel.md](../../reference/control-channel.md)):

```text
wire   = 0x01 (write-prefix) + AES-CCM( command + body + trailer[4] )
```

The `0x01` write-prefix is **not** part of the encrypted plaintext — the plaintext
starts at the `command` byte (confirmed live: `0x01`+enc(`4f00158b3609`) answers;
`0x01`+enc(`014f00158b3609`) is ignored). The 4-byte trailer is a session/sequence
tail the lock **does not validate** for reads — a captured cross-session value
(`158b3609`) elicits valid responses for `0x4f` and `0xde`. `build_read_query_write`
emits this shape; `U200Client.battery()` uses it.

Confirmed live 2026-08-25 (own lock, own account):

| Read | Sent plaintext | Decrypted response | Decode |
| --- | --- | --- | --- |
| `GET_BATTERY_INFO` `0xde` | `de 00 158b3609` | `de00 07000101 30 0000 c70a` | **byte 6 = 0x30 = 48 %** ✅ |
| `BATTERY` `0x4f` | `4f 00 158b3609` | `4f00 0000 a812` | payload 0 (a different, unused metric) |
| `LOCK_STATUS` `0x07` | `07 00 158b3609` | `07 00 <s> 00000000 00 <crc16>` | **byte 2 bit `0x02`: set = unlocked, clear = locked** ✅ |
| `TONGUE_STATUS` `0x08` | `08 00 158b3609` | `08 00 0000 ba17` | responds (payload `0000` in both states so far) |
| `GET_LIMIT_INFO` `0xe2` | `e2 00 158b3609` | `e2 00 0100 c71b` | responds (calibration limits) |

`LOCK_STATUS` (`0x07`) correlated live with ff62 (0x1d/0xdd): `0x04` = locked,
`0x06`/`0x0b` = unlocked — the discriminator is **bit `0x02`** of the status byte
(bolt-retracted flag). `GET_DOOR_LOCK_STATUS` (`0xe5`), `REPORT_LOCK_STATUS`
(`0x15`) and `HANDLE_DIRECTION` (`0x30`) do **not** answer an on-demand read.

### Full SYSTEM read sweep (feature 030)

All 50 SYSTEM read-only opcodes were swept live with `build_read_query_write`
(`0x01` prefix), read-only, no actuation. **21 answer**; the rest (WiFi/Zigbee/UWB
/face/temp-open) return nothing — features this U200 lacks or that use another
family. Response shape is always `<opcode> 00 <payload> <crc16>`.

| Opcode | Name | Response | Notes |
| --- | --- | --- | --- |
| `0x4d` | DEVICE_MTU | `4d00 f700 d311` | `0x00f7` LE = **247** (ATT MTU) |
| `0xde` | GET_BATTERY_INFO | `de00 07000101 30 0000 c70a` | **48 %** |
| `0x07` | LOCK_STATUS | `0700 06 …` | bit 0x02 = unlocked |
| `0x0d` | FIRMWARE_VERSION | `0d00 03000000 0055 00 3b44` | version block |
| `0xe0` | GET_DOOR_LOCK_TYPE | `e000 0101 4b19` | payload `01 01` |
| `0xee` | GET_LOCK_WORK_MODE | `ee00 0004 6e` | payload `00 04` |
| `0xae` | GET_AUTO_LOCK_TIME | `ae00 05 000000… adbe` | byte2 `0x05` |
| `0xd6` | GET_AUTO_LOCKUP_DELAY_TIME | `d600 0000 fe18` | payload `00 00` |
| `0x8e` | QUERY_MOTOR_DIRECTION_AND_TORQUE | `8e00 00ff 2ee1` | payload `00 ff` |
| `0xc0` | GET_OPEN_DOOR_DIRECTION | `c000 0004 8a` | payload `00 04` |
| `0xc5` | GET_AUXILIARY_LOCKING | `c500 0000 141b` | payload `00 00` |
| `0xe9` | GET_ASSIST_TURN | `e900 0084 7f` | payload `00 84` |
| `0xe4` | GET_PULL_SPRING | `e400 010200 9be9` | payload `01 02 00` |
| `0xec` | GET_SILENT_CONTROL_LOCK | `ec00 03 0000… 6899` | byte2 `0x03` |
| `0xe2` | GET_LIMIT_INFO | `e200 0100 c71b` | calibration limits |
| `0xcb` | GET_ALARM_ENABLE | `cb00 0084 b3` | payload `00 84` |
| `0xd8` | GET_ADVANCED_MODE | `d800 0004 da` | payload `00 04` |
| `0x33` | TIMEZONE_TIME | `3300 3006` | payload `30` |
| `0x08` | TONGUE_STATUS | `0800 0000 ba17` | constant so far |
| `0xf3` | GET_GOOGLE_VOICE_UNLOCK_STATE | `f300 00000000000000 04 62` | |

`DEVICE_MTU` (247) and battery/lock-status decode cleanly; the rest have raw
payloads whose units/enums need either a labelled sample (change the setting in the
app, re-read) or the app's decoder. `U200Client.read(opcode)` and `aqara read
<name>` expose all of them raw; `system_read_opcodes()` lists them.

`0x4f` (BATTERY) answers but reports `0`; the live-usable charge is `0xde`
(GET_BATTERY_INFO). The `REPORT_*` battery opcodes (`0x0a`/`0x50`/`0x77`) do **not**
answer an on-demand read (they are push-only). This same shape should unlock the
other catalogued reads (status, settings) — send `command + body + trailer` behind
the `0x01` prefix, not the bare opcode.

## Write/SET opcodes (byte-confirmed 2026-08-28, app-driving + btsnoop)

Reverse-engineered by driving the official app (autonomous adb/uiautomator + a Zigbee
Fingerbot to pass the keypad gate) to change a setting while the phone's BT HCI snoop
was on, then keystream-decoding the captured write. Both confirmed against the read value.

| Setting | READ | WRITE (SET) frame | Values |
| --- | --- | --- | --- |
| Voice volume | `0xc3` | `02 04 <level>` (op `0x02`, kind `0x04`) | `01`=Alto, `02`=Medio, `03`=Bajo |
| Alarm volume | `0x84` | `83 02 <val> 07` (op `0x83`, kind `0x02`) | `00`=Silencio, `0x10`=Normal |
| Turn assist | `0xe9` | `e8 <0/1> 68 …` (op `0xe8`) | `00`=off, `01`=on |
| Verify-fail lockout ("Bloqueo de verificación") | `0xb0` | `af <seconds:4 LE> <trailer:2>` — `af780000000c4a` | 120s (2 min) confirmed; `build_set_verify_fail_time()` |
| Auto-lock re-lock delay ("Re-bloqueo de seguridad" timer) | `0xd6` | `d5 <seconds:2 LE> <trailer:2>` — `d50a000efe` | 10s confirmed; `build_set_auto_lockup_delay_time()` |

Method (repeatable for every setting): app → open the setting (keypad gate: close the
popup, tap a keypad key / fire the fingerbot, re-enter fast) → select a value → the app
writes the SET frame on ff61 → `adb bugreport` → extract `FS/data/misc/bluetooth/logs/
btsnoop_hci.log` → `scratchpad/app_keystream.py` decodes it (static-nonce keystream reuse).
This yields BOTH the enum byte-mapping and the SET opcode, so the library can WRITE
(control), not just read. Actuation `0x74` stays out of scope by default.

### 2026-08-28/29 settings sweeps — auto-lock and silent-mode byte layout

First pass (2026-08-28) changed several settings per connection, which muddied
which byte moved for which action. A 2026-08-29 follow-up re-ran the loop
**isolating one field per connection** (nothing else touched) and resolved
most of it:

- **`0xc4` SET_AUXILIARY_LOCKING — fully resolved, now confirmed and wired
  in** (`build_set_auxiliary_locking_on_close_enabled()` /
  `_relock_enabled()`). It's a **single opcode covering both auto-lock
  sub-toggles**, disambiguated by a `kind` byte: `c4 <kind> <val:2>
  <trailer=0x98>`. Isolated captures: `kind=0x02` (`c402000698`) enables
  "Bloqueo automático al cerrar"; `kind=0x04` (`c404000098`) enables
  "Re-bloqueo de seguridad". `val` differs by toggle (`0x0006` vs `0x0000`)
  but its exact meaning is unconfirmed — no OFF-state frame was captured for
  either toggle, so only the two ENABLE frames are exposed as builders.
- **`0xad` SET_AUTO_LOCK_TIME — DOES NOT EXIST for this; fully resolved as a
  dead end.** The 2026-08-29 isolated toggle captures never produced it (only
  `0xc4` did), so a follow-up isolated capture changed a sub-timer's VALUE
  instead (the "al cerrar" timer, 10s→5s) expecting to finally trigger 0xad —
  instead it produced **`d5 05 00 01 fe`: the SAME opcode as the OTHER
  auto-lock timer** (`0xd5`, previously thought to be re-lock-delay-only).
  `0xd5` covers BOTH timers, disambiguated by the first trailer byte
  (`0x0e`=re-lock, `0x01`=on-close) — see the confirmed-operations table
  above and `build_set_auto_lock_on_close_delay_time()`. The earlier
  2026-08-28 13-byte `0xad` sample was therefore something unrelated (never
  reproduced across three follow-up isolated captures); don't chase it
  further.
- **`0xeb` SET_SILENT_CONTROL_LOCK — pattern confirmed across two separate
  days' captures, still not fully wired.** Structure `eb <schedule:1>
  <speed:1> <9 more bytes> <2 unrecovered bytes>`. `schedule` (byte1) is `00`
  when "Modo silencioso programado" is off, `01` when on — confirmed in both
  the 2026-08-28 sample and a fresh 2026-08-29 isolated capture (only this
  toggle changed, both speed pickers left at "Rápido"/"silencioso"):
  `eb 01 03 30 2c 93 6a d0 b8 93 6a 00` (+2 unrecovered bytes). `speed`
  (byte2) tracks the "Desbloquear/Bloquear configuraciones" picker and looks
  like a 1-based index matching the UI order (Tranquilo/estándar/Rápido) —
  `02` when that picker was "estándar" (2026-08-28), `03` when it was
  "Rápido" (2026-08-29) — but only two data points, not fully proven. Bytes
  3-11 changed completely between the two days despite the schedule window
  defaulting to the same 21:00–07:00 both times, which rules out the earlier
  "fixed schedule padding" theory — they're more likely a session/timestamp
  field unrelated to user-visible settings. Not wired as a writer: the
  trailing 2 bytes are still uncaptured and the middle field is unexplained.

### 2026-08-30 — LANGUAGE (0x03) byte-position corrected; Español blocked by an app bug

**Correction of the original 2026-08-29 note (kept for history below):** the
language code is **byte1**, not byte2 — byte2 (`0x83`) is a constant marker
present in every SET_LANGUAGE frame, not "English's code". The earlier note
conflated the two because it only had one confirmed sample. Frame:
`03 <code:1> 83 <trailer = code XOR 0x05>`.

Re-derived live with two independent isolated captures, each verified two
ways — an explicit lock-side ACK (`03 00 00 06 00`, present for both) and a
fresh cold app relaunch confirming the real device state:
- English: `code=0x02` → `03028307` (trailer `0x02^0x05=0x07`) — matches the
  original 2026-08-29 capture byte-for-byte, just reinterpreted correctly.
- Deutsch: `code=0x09` → `0309830c` (trailer `0x09^0x05=0x0c`).

**Español's code is still unknown, and the lock is currently left on Deutsch
as a result — see below.** `code=0x0a` was tried (extrapolating the
sequential/XOR pattern) and is confirmed **wrong**: no ACK followed the write,
and a fresh cold relaunch still showed Deutsch as the real state.

**The official app itself is bugged for this specific flow on this app
version**, independent of any capture issue: "Sonido de voz > Selección de
idioma > Otros idiomas" opens a picker sheet (中文 / Polski / Русский /
Español(Descargado) / Français) where tapping **any** row — tested on both
Español and Français, 5+ attempts, explicitly ruling out the keypad-gate
dialog stealing the tap each time via before/after screenshots — closes the
sheet as a no-op: no checkmark ever appears, the "Confirmar"/"Descargar y
usar" button never activates, and no BLE write happens. Direct D-pad
navigation (bypassing touch entirely) also found no focusable row, confirming
this is a real app-side interaction bug, not a coordinate or timing issue in
the automation. Consequence: the app UI currently cannot be used to select
**any** language from that sub-sheet, not just Español — English and Deutsch
only work because they have dedicated quick-select chips in the flat list one
level up, which behave completely differently (direct single-tap select, no
sub-sheet, no bug).

**Result: the lock's spoken-prompt language is left on Deutsch at the end of
this session**, not restored to its original Español, because neither the app
UI nor a confirmed byte value could get it back. This is an audio/voice
setting only — it does not affect lock/unlock, security, or any BLE control
function. To fix: either (a) retry the app flow after an app update in case
this gets patched, or (b) send `build_control_frame(0x03, bytes([code, 0x83,
code ^ 0x05]))` directly via a raw `U200Client`/`GattClient` session for a
candidate Español code and check for the ACK — English=2 and Deutsch=9 are
the only two data points; do not extrapolate further without live
verification.

**2026-08-30 (later, wire-level proof):** after a fresh app login (the
session had been logged out) plus a scroll-then-tap on the sub-sheet, the
"Español(Descargado)" row DID show a selection state this time (the button
changed from "Descargar y usar" to "Confirmar" — unlike the 5 earlier
attempts, which never got that far). Tapping "Confirmar" was captured on a
fresh HCI snoop: **zero SET_LANGUAGE (0x03) writes appear anywhere in the
connection** — only two `680168` LANGUAGE READ queries (the screen's normal
load + a post-tap refresh), both still reflecting Deutsch. A cold relaunch
afterward confirmed the real device state is still Deutsch. So the bug is
narrower than first thought: the picker CAN reach a "selected" visual state
for Español, but its Confirm handler still doesn't fire a write for it —
proven with wire-level evidence this time, not just a UI observation.

**2026-08-30 (resolved) — the real mechanism is a bulk OTA file transfer, not
a short control-channel command.** The user's hypothesis was right in
spirit: language material is a downloadable **package**, and the app's
"Otros idiomas" picker bug only blocks the *row selection* via synthetic
touch (a real human touch on the phone worked every time) — once a real tap
selects a row and "Descargar y usar"/"Confirmar" is tapped, the download
proceeds normally. Captured the full flow live (Français, then Español,
both freshly downloaded): the voice pack is transferred over a **separate
GATT characteristic (ATT handle 60, NOT the AES-CCM control channel on
handle 49)**, using write-prefixes `0x11`/`0x90`, in ~9,000+ chunks of up to
244 bytes for a single language. Crucially **this channel is NOT encrypted
with the session's AES-CCM cipher** — the chunks contain directly-readable
ASCII: a manifest of `<name>.lst`/`<name>.mp3` pairs (e.g.
`fr_Passage_mode_is_available.mp3`, `es_Addedsuccessfully.mp3`), i.e. the
lock's spoken-prompt library, one file per phrase. **The control channel
(handle 49) carries ONLY periodic keepalives during the entire transfer —
no `0x03` SET_LANGUAGE write appears anywhere.** So the actual
"switch active language" signal is embedded in the OTA protocol itself
(handle 60), not the short `03 <code> 83 <trailer>` frame documented above.

That `03 <code> 83 <trailer>` frame is real and reproducible (confirmed with
ACKs for English/Deutsch) but appears to be a **separate shortcut path**
used only when picking a language from the flat list's quick-select chips
(a language the app has fully cached, e.g. immediately after downloading
it) — not the general mechanism. Reproducing the full OTA protocol (framing,
chunk sequencing/ack, and the exact "activate" trigger at the end) is real
future work for making language changes fully autonomous in `aqara_ble`
(the user's ask) — it needs its own capture-and-decode session focused on
handle 60, ideally with an HTTP capture of the manifest-download API call
too (not done this session — noted as a gap).

**Practical result: the lock's language was successfully restored to
Español** by forcing a fresh download (selecting a different language
first evicts the cached one — the app's own dialog warns "el material en
idioma actual se eliminará y reemplazará" — after which Español itself
shows as needing download again and can be re-downloaded to reactivate it).
Confirmed via a full cold relaunch. A real per-touch synthetic-vs-human
input quirk was also identified: `adb shell input tap` never registered a
row selection for anything requiring a download (Français, 中文, Русский,
Español-when-not-cached) even at correct coordinates — only a real human
touch on the phone worked; the row selection state itself doesn't render in
`uiautomator dump`'s plain text/bounds either (needs a screenshot to see
the checkmark), which caused an earlier false "still broken" read on this
same session — worth remembering for future automation of this screen.

Only `build_set_language_english()` and `build_set_language_deutsch()` are
exposed as builders (the confirmed shortcut-path frames); the general OTA
download mechanism is not implemented in the library yet.

#### 2026-08-31 — OTA handle-60 framing, first byte-level capture

Live capture (adb HCI snoop, a fresh Français download from "Otros
idiomas" — the synthetic-tap picker bug from the note above did **not**
reproduce this time; `adb shell input tap` selected the row and reached
"Descargar y usar" fine) confirms the wire shape the earlier session could
only infer from the app's decompiled code:

- **Transport confirmed:** ATT handle `0x003c` (60, decimal), opcode `0x52`
  (**Write Command** — fire-and-forget, no ATT-level response expected; no
  `0x1b` Handle Value Notification was ever seen on this handle in the
  capture, so any pacing/ack the lock does happens above the ATT layer, not
  as a visible BLE ack). Chunks are ≤244 bytes, write-prefix `0x11` on
  every single chunk (matches the `0x11`/`0x90` prefixes noted 2026-08-30;
  only `0x11` appeared for a download in this capture).
- **First chunk is a plain-ASCII init frame:** `11 0100 ff
  "U200_FR_audio_burn.bin"00"1664596"...` — i.e. `<prefix=0x11> <seq:2 LE,
  starts at 1> <marker, starts at 0xff> <bundle filename ASCII> <NUL>
  <total size in DECIMAL ASCII digits> ...`. The size string
  (`1664596` bytes here) is the whole bundle for one language, matching
  the "~9,000+ chunks" scale already documented (1664596 / 244 ≈ 6822
  chunks).
- **The next several chunks carry the file manifest in plain ASCII**,
  confirming the `<name>.lst`/`<name>_<Name>.mp3` pairing already
  documented, but interleaved with 4-byte little-endian numeric fields
  (plausibly per-entry byte offset/length into the bundle) whose exact
  layout is **not decoded** — only the ASCII spans were trustworthy enough
  to assert. The `marker` byte counts DOWN from `0xff` across these
  chunks (`0xff`, `0xfe`, `0xfd`, `0xfc`, `0xfb`, ...) while the leading
  2-byte field does not follow a simple flat LE counter — a real
  structure is there, but pinning it needs a dedicated, uninterrupted
  capture-and-diff session (this one was captured mid-transfer via a
  `bugreport`'s rolling buffer, not from a clean start).
- **After the manifest, the remaining chunks are opaque binary** (compiled
  audio-codec data, not text) — expected and NOT a contradiction of the
  "plaintext, unencrypted channel" finding: unencrypted just means no
  AES-CCM is applied, the bytes are still compressed/encoded audio.
- **The app's own progress UI is unreliable for judging whether a transfer
  is actually running.** The "0%" download screen stayed frozen at 0% for
  5+ minutes with the keypad-presence gate re-triggering only once, while
  the pulsador was re-fired every ~10-15s to keep the connection alive —
  looked exactly like a hung transfer. A `bugreport` pulled at that exact
  moment (while the UI still showed "0%") captured **18,067** real
  handle-60 `WriteCmd` chunks already in flight. **Don't abandon a
  same-looking "stuck at 0%" session based on the UI alone next
  time — check the HCI snoop first.**
- The transfer was manually abandoned ("Abandonar") before completion once
  the capture was secured, specifically to avoid an indefinite live
  BLE session on the maintainer's real lock; the language reverted cleanly
  to Español on abandon (confirmed via the settings screen re-reading
  "Español" with no lock/app side-effects), so **the exact "activate"
  trigger frame at the end of a completed transfer is still not
  captured** — that remains the one open piece for full automation.
- `adb bugreport`'s `dumpstatez` service intermittently refused two
  connection attempts in a row before a third succeeded — a transient
  device-side hiccup, not a real blocker; retry if it happens again.

#### 2026-09-01 — the "activate" trigger frame, TWO independent captures (Français + Español)

The one open piece flagged above — the exact end-of-transfer activation
frame — is now captured **twice, from two genuinely independent completed
transfers** (a Français download that ran to completion, and a later
Español download that also ran to completion after fixing an unrelated
Bluetooth-proxy outage), letting the shape be told apart from any
per-transfer noise. Both transfers, immediately after the last real audio
chunk, end with the **exact same sequence of frame types in the same
order**, all still on handle `0x003c` / write-prefix `0x11` unless noted:

1. One all-`0xFF` padding chunk (244 bytes).
2. One all-`0x00` padding chunk (244 bytes).
3. Two all-`0x1A` marker chunks (244 bytes, then a shorter 58-byte one).
4. A tiny 2-byte frame: `11 04`.
5. **Two identical** 134-byte frames shaped exactly like the transfer's own
   init frame but zeroed out: `11 0100 ff <244 bytes... all 0x00>` — i.e.
   the same `<prefix><seq=1><marker=0xff>` header as the very first chunk
   of the transfer, this time with an empty/zeroed body instead of a
   filename+size string. Sent twice, back to back, byte-identical both
   times within each transfer.
6. **Two identical** 17-byte frames using a **different write-prefix,
   `0x90`** (every other frame in the whole transfer uses `0x11`):
   - Français: `90 1b7da3a951649f46b00a6e18acae2823`
   - Español: `90 dc885ae8e29acad7d35ae75772fef244`

The structural shape (padding → marker → `11 04` → zeroed-init-repeat ×2 →
`0x90`-prefixed 17-byte frame ×2) is now confirmed language-independent —
this is very likely the real "commit/activate this language now" signal
the app sends once it's satisfied the transfer landed cleanly, replacing
the earlier open question with a concrete, reproducible sequence.

**Follow-up, same session, THIRD data point — content ruled out, points at
a phone/app-side rotating value instead.** Ran the exact isolation
experiment this section originally proposed: downloaded Français a
*second* time (same bundle content and size as the first Français
capture above), immediately after the Español download completed. Result:

| Download | Order | `0x90` payload |
| --- | --- | --- |
| Français (1st) | 1st | `1b7da3a951649f46b00a6e18acae2823` |
| Español | 2nd | `dc885ae8e29acad7d35ae75772fef244` |
| Français (2nd) | 3rd | `dc885ae8e29acad7d35ae75772fef244` |

The 2nd and 3rd rows are **byte-identical** despite different content
(Español vs. Français — different bundle, different size, different
manifest) and a completely separate BLE connection/session for each. This
**rules out both of the two leading candidates**: it is not a hash/CRC of
the transferred bundle (different content, same value) and not a
per-connection nonce (different BLE sessions, same value). The 1st and
2nd/3rd rows differ despite rows 1 and 3 sharing identical content
(Français both times) — so it isn't a per-language constant either.

The 2nd and 3rd downloads were ~28 minutes apart by the capture
timestamps, one order of magnitude longer than the offline-password
feature's 10-minute rotation grid, so a short time-windowed rotation (the
first instinct, given that other feature's precedent) doesn't fit
either — 28 minutes elapsed with zero change. What *did* happen between
the 1st Français capture and the 2nd/3rd (which share their value): a
long gap of unrelated work (over an hour) during which the Aqara app was
**force-stopped and cold-relaunched several times** (chasing an unrelated
Bluetooth-proxy outage), while between the 2nd and 3rd captures the app
process ran continuously with no restart. **Leading hypothesis, not yet
confirmed**: this value is generated once per app **process lifetime**
(e.g. a random token/nonce the app creates at cold start and reuses for
every OTA activation until it next restarts), not derived from the
transfer's content or its BLE session at all. Confirming this needs one
more data point: force-stop and cold-relaunch the app, then download any
language and check whether the `0x90` payload changes from
`dc885ae8e29acad7d35ae75772fef244` — if it does, the per-process-lifetime
theory is confirmed (and the value must come from somewhere restart-reset
on the phone, e.g. a fresh CSRNG draw kept in memory, needing a live
Frida hook to actually observe rather than infer); if it stays the same
even across a restart, look toward something persisted to disk instead
(shared prefs / local DB row) that a plain force-stop doesn't clear.
`aqara_ble` still only exposes `build_set_language_english()`/`_deutsch()`
(the cached-language shortcut path); a real `OtaLanguageTransfer` builder
covering the full download+activate sequence is blocked on nailing this
one field, not on anything else in the framing above.

#### 2026-09-01, later same day — live Frida Java-hook capture: a 4th data point that complicates the picture (two DIFFERENT `0x90` frames, not an identical pair; source still not found)

Confirmed the previous session's Frida 17.2.12 finding is real and durable:
a `Java.perform()` hook (`SecureRandom.nextBytes`, `UUID.randomUUID`,
`MessageDigest.digest`, `BluetoothGattCharacteristic.setValue`) stayed
attached through roughly 40 minutes of real app navigation — menu
traversal, three keypad-gate cycles, two full download attempts — with
zero SecNeo crash. This is now solid enough to consider promoting 17.2.12
to the project's daily driver (see `frida-repack-strategy.md`).

**The capture itself, triggered live** (re-downloaded Français while the
hook was attached): two `BLE setValue` hits fired almost immediately after
tapping "Descargar y usar", **not** at the end of a long transfer:

```text
[BLE setValue] len=17 hex=90 2f d5 ef 63 68 a3 93 57 88 ec 7d 61 af 3e 57 bf
[BLE setValue] len=27 hex=90 2f d5 ef 59 58 e0 dd 10 9f e3 30 4d 56 2d 4a 3a
                          7c a4 24 9f 5d 89 6d 43 e9 0c
```

This does not match the shape documented above ("two **identical** 17-byte
`0x90` frames at the very end of a completed transfer"). Instead:

- The two frames here are **different lengths (17 vs 27) and different
  content** — not a repeated pair.
- They share a 4-byte prefix, `90 2f d5 ef`, then diverge completely.
- They fired **before any bulk `0x11` data chunk was ever observed** by
  the hook (which was watching for byte[0] ∈ {0x11, 0x90} on every
  `setValue` call) — and after these two frames, the download stalled at
  0% and the app re-asked for the keypad-gate wake, i.e. the real transfer
  had not actually started yet.

**Working theory, not confirmed**: these are a *different* `0x90`
exchange from the one documented earlier — a short session-establish/
handshake pair sent at the *start* of an OTA request (possibly to arm the
keypad-wake requirement or negotiate a transfer session id), distinct from
the *end*-of-transfer activation pair captured previously. The shared
`2f d5 ef` prefix is a plausible session/sequence identifier for this
specific exchange. This session never got far enough to also observe the
end-of-transfer pair again, because:

**New instability, also worth recording**: two separate download attempts
this session (a fresh Polski download, then the Français re-download
above) both stalled at 0% indefinitely after the initial handshake and had
to be manually abandoned — a regression from prior sessions, where full
transfers completed in a few minutes. `adb logcat` showed the BLE GATT
link renegotiating PHY repeatedly (`onPhyUpdate` alternating 1x/2x every
30–45s) but no explicit error. Two candidate causes, neither confirmed:
(a) the Frida hook's own overhead — constructing a `Throwable` and walking
`getStackTrace()` on *every single* `setValue` call — could be slow enough
to desync a time-sensitive BLE write/ACK handshake during the real bulk
transfer; (b) a genuine, hook-unrelated network/CDN hiccup fetching the
voice-pack asset. **Next session should retry a full download with the
hook detached (or a leaner hook that skips the backtrace on non-matching
writes) to isolate which.**

**Source hunt: still open.** None of `SecureRandom.nextBytes`,
`UUID.randomUUID`, or `MessageDigest.digest()` (no-arg overload) fired
with a matching value in the moments immediately before either write —
ruling out those three specific Java-level RNG/hash paths as the direct
source of this particular exchange's bytes. Not yet hooked: `MessageDigest
.digest(byte[])`/`.update()` (only the no-arg overload was hooked), and
`javax.crypto.Cipher.doFinal()` — a strong candidate given the project's
existing evidence that BLE payloads are AES-encrypted with a cloud-KDF
session key ([[app-reads-settings-bulk-blob]]). Next attempt should add a
`Cipher.doFinal` hook alongside the existing three.

**Loose end for next session**: while restoring the phone's language back
to Español (the session's baseline) at the end of this investigation, the
"Confirmar" write for an already-downloaded language (no OTA needed, just
a small opcode) did not visibly take effect — the settings screen kept
showing "Deutsch" after two clean confirm attempts. Given the PHY-
renegotiation instability noted above, this is likely the same BLE
flakiness rather than a new protocol finding. **The physical lock's voice
language may currently be left on Deutsch, not Español — verify and fix
next session** (quick top-level pick, no download needed, once the BLE
link is stable again).

#### Original 2026-08-29 note (superseded above, kept for history)

`03 02 <val> 07` — same `kind=02`/`trailer=07` shape as `SET_DOORLOCK_ALARM_VOLUME`
(0x83). Confirmed live switching "Sonido de voz > Selección de idioma" to
English: `val=0x83`. This is **not** a sequential 0-6 index across the 7
languages the app lists — 0x83 is far too large for that, so it's very likely a
shared cross-device Aqara language-code table (same codes used by other Aqara
products). Trying to revert to Español (already downloaded, so no voice-pack
fetch needed) **did not produce a matching wire write** in two more capture
attempts, even though the app's UI updated to show "Español" both times and a
fresh app relaunch + re-read afterward confirmed the lock's actual state really
is Español again — so either that path uses a different frame this session's
captures didn't isolate (a fully-fresh reconnect right at the moment of tap
might be needed), or same-value / cached-language switches skip the wire write
entirely and rely on some other sync path.

### "Registro" (access/activity log) — first live probe, clean negative (2026-08-31)

The lock's own opcode catalog has two LOG-family log-sync opcodes,
`SYNC_DOOR_LOCK_LOG` (0x12) and `SYNC_LOG` (0x13), plus two SYSTEM-family
push-style ones, `REPORT_LOCK_LOG` (0x1D) and `REPORT_DOOR_LOG` (0x1E) — all
name-only until now, never captured or probed. First live attempt, over the
ESP32-S3/bumble transport (freshly reflashed this session — it wasn't dead
hardware, just a corrupted prior flash; `esptool erase_flash` + rewrite fixed
it, verified end-to-end: `hci_smoke.py` + a real scan finding the lock):

- **`0x13` (`SYNC_LOG`) was deliberately NOT sent.** It's the one LOG opcode
  that collides on the wire with a SYSTEM/USER opcode from a *different*
  family — specifically `USER.ADD_VISITOR_PWD`, also `0x13`. Since
  `operations_catalog.py`'s own foundational assumption ("no mainCmd byte on
  the wire — sub_cmd alone identifies the command", see
  `build_control_frame`'s docstring) was only ever validated against the two
  confirmed SYSTEM commands (`0x74`/`0x2f`), there's no evidence it holds for
  a byte value shared across families. Sending it risked an ambiguous
  interpretation touching visitor-password/credential state — skipped outright
  rather than guessed at, consistent with the standing rule to never touch
  user-management surfaces on the real lock.
- `0x12` (`SYNC_DOOR_LOCK_LOG`) — **no collision** with any other catalogued
  opcode, tried both with the standard read shape (`12 00 158b3609`, ff61
  prefix `0x01`) and with the LOG-family prefix `0x03` (documented for its
  sibling `0x13`/`0x1f`/voice-OTA `0xa6`) — **`responded=False` both times.**
- `0x1D`/`0x1E` (`REPORT_LOCK_LOG`/`REPORT_DOOR_LOG`) — standard read shape,
  prefix `0x01` (their family default) — **`responded=False` both times**,
  consistent with the established pattern that `REPORT_*` opcodes are
  push-only and never answer an on-demand read (same as `REPORT_BATTERY`,
  `REPORT_VOLUME`, etc. — see the "Full SYSTEM read sweep" section above).

**Conclusion (real negative, not yet a dead end):** none of the four
opcodes/shapes tried elicit a response. This doesn't mean "Registro" is
unreadable — only that the generic read shape that works for most SYSTEM
opcodes doesn't apply here as tried, confirmed below by static analysis of
the app's own source.

#### 2026-08-31 (later) — static analysis of the app's own source finds the real recipe

Went back into the U200 plugin's decompiled JS (`u200_decompiled.js`,
818K lines, already extracted this session) looking for the real
`SYNC_LOG`/`SYNC_DOOR_LOCK_LOG` call sites — this time searching for the
actual **request-builder function**, not just the opcode-name constants
table (which was already cross-checked earlier). Found it, and it explains
everything the live probe couldn't:

- **The app's own `BleCmd.ts` constants module was found in full** (not
  just referenced) — an object literal with `SendMainCmd`
  (`{SYSTEM:'01', USER:'02', LOG:'03', ALARM:'04', DEVICELOG:'05', XXQ:'06',
  SYSTEM_EXT:'07', LONG:'3f'}`), `ReplyMainCmd`, and every per-family
  `*SubCmd` table (`SystemSubCmd`, `UserSubCmd`, `LogSubCmd`,
  `DeviceLogSubCmd`, `AlarmSubCmd`, `XXQSubCmd`) — **byte-for-byte identical**
  to `operations_catalog.py`. This is a stronger confirmation than the
  earlier opcode-table cross-check (that came from a name→hex dictionary
  found once; this is the literal constants file the running app code
  imports and uses on every single BLE call), and closes out any remaining
  doubt about the family-grouping/naming for SYSTEM/USER/LOG/ALARM/DEVICELOG.
- **Found the real `SYNC_LOG` request builder** (a generator function whose
  console.log calls are in Chinese: `'请求日志列表开始索引 : '` = "Request log
  list start index: ", `'  结束索引 : '` = "end index: "). It builds:
  ```
  { mainCmd: SendMainCmd.LOG,       // '03'
    subCmd:  LogSubCmd.SYNC_LOG,    // '13'
    data:    reverseByteHex(toHex(startIndex), 4) + reverseByteHex(toHex(endIndex), 4) }
  ```
  i.e. **the body is TWO little-endian uint16 indices (4 bytes total)** —
  not the generic single `0x00` placeholder byte our `build_read_query_write`
  sends for status-style reads. This alone explains the earlier
  `responded=False`: even if `0x13` were safe to send, our placeholder body
  was the wrong shape for this opcode's actual parameters.
  It's then passed as a **structured object** (`{mainCmd, subCmd, data}`) to
  a `sendBlePackageAsync()` function, not as pre-assembled wire bytes — so
  whether `mainCmd` becomes a literal byte on the wire, or is purely an
  app-side dispatch/response-routing key (with the *reply's* mainCmd, e.g.
  `0x83` for LOG vs `0x82` for USER, being what actually disambiguates a
  colliding request subCmd like `0x13`), is **still not resolved** from
  static analysis alone — only a live capture of the real wire bytes would
  settle it.
- **Found the reply parser too**: `parseLogData(hexString, outArray)` walks
  the response as a sequence of TLV-shaped records — for each: a 2-byte
  field (purpose unconfirmed, likely an index/id), then a 1-byte length,
  then that many bytes of payload — repeated until the buffer is exhausted.
  This is the shape to decode against once a real response is captured.
- **`SYNC_DOOR_LOCK_LOG` (0x12) — the one opcode we tried live with no
  collision risk — has ZERO call sites anywhere in this compiled bundle.**
  Not "hard to find": grepped for every property-access form and it simply
  isn't invoked. This independently explains that specific live negative
  without needing a wrong-frame-shape theory — this U200 firmware/app
  version's "Registro" screen most likely never uses it at all, `SYNC_LOG`
  alone covers the feature, and `SYNC_DOOR_LOCK_LOG` may be vestigial from a
  shared codebase with another lock model.
- A red herring worth recording so it isn't re-chased: a class named
  **`LockRecordHandler`** looked like the obvious candidate by name, but its
  actual content (`notifyLockBusy`/`notifyLockFree`/`ifLockBusy`/
  `startBusyTimeout`) is a **BLE-session busy-mutex coordinator** — "Lock" as
  in *mutex*, "Record" isn't even the right word for what it does. Nothing
  to do with the access-log feature.
- Separately, a **`LogTransferHandler`** class (Chinese debug strings:
  receives chunked data, ACKs on a `0xfe` terminator byte, can zip and
  **upload** the result via `uploadFileWithFileName`) exists for
  `DEVICELOG.SYNC_DEVICE_LOG` (mainCmd `0x05`) — this looks like a
  diagnostic-log-to-support-team uploader, a **different feature** from the
  user-facing "Registro" list, not yet fully disentangled from it with
  certainty.

**Why `0x13` still wasn't sent tonight, now with a concrete recipe in hand:**
the collision with `USER.ADD_VISITOR_PWD` is unresolved by any of the above —
if anything, finding that the app treats `mainCmd`/`subCmd`/`data` as
separate structured fields (not a single pre-built byte string) makes it
*more* plausible that something besides the raw subCmd byte disambiguates
them, which is a reason for hope, not a green light to guess it's safe live.
The path to actually testing this stays the one already documented: capture
the app's own real request live (write-opcode RE loop, 3d) — a live capture
would show, in one shot, whether the wire bytes for a real
`SYNC_LOG` request differ visibly from `ADD_VISITOR_PWD`'s, settling the
ambiguity with evidence instead of a guess. Until then, `0x13` is not sent
by this library.

#### 2026-08-31 (later still) — live HTTPS capture: "Registro" is NOT re-fetched over the network

Attached the native SSL hook (`capture_ssl_native.js`, left running across the
whole navigation — it writes to a file, so it survives repeated screen
transitions unlike a PTY-logging hook) and drove the real "Registro" screen
three separate ways while the lock was BLE-connected (`Bloqueado` state,
live): (1) opened the screen fresh, (2) switched the "Todos los
eventos"/"Eventos de desbloqueo" filter tab, (3) opened the date picker and
selected a day (2026/08/30) far from anything that could plausibly be
preloaded. **None of the three produced any new SSL traffic** — the capture
file's line count did not grow (screen open) or grew by only one unrelated
17-byte keepalive-shaped frame (tab switch, date change). Meanwhile the
list content itself (today's `Bloqueado exitosamente 08:19` /
`Puerta Desbloqueada 08:11`, yesterday's full history including
`Esther desbloqueado con Contraseña`) rendered correctly every time.

**Conclusion:** this screen's data is NOT fetched fresh over HTTPS on open,
filter, or date-change — it is served entirely from a local store already
populated on the phone (RN AsyncStorage/SQLite, or synced once earlier and
cached indefinitely). This means the `SYNC_LOG` (0x13) BLE opcode invesitgated
above is very likely how that local store gets **populated in the first
place** (at pairing, or periodically in the background) rather than
something fetched live on every screen visit — consistent with, and refining,
the static-analysis finding that `SYNC_LOG`'s request builder takes a
`startIndex`/`endIndex` pagination range (a local-store catch-up sync
primitive, not a per-view live query). Does not change the 0x13/collision
open question from the static-analysis section above; only rules out "just
capture the HTTPS call instead" as a shortcut for this specific feature — a
real "Registro" capture still needs the BLE 0x13 wire bytes, ideally from a
brand-new pairing (see `docs/reverse-engineering.md` §3g, the device-binding
capture) where the local store is provably empty beforehand.

### "Modo de cierre nocturno" — confirmed NOT a BLE/HTTPS lock command

See [[night-latch-is-not-a-lock-command]] (memory) / the exhaustive investigation
2026-08-28: two clean BLE captures (enable, disable) plus a live Frida MITM (native
SSL hook on a repacked app) all showed **zero** lock-control traffic for this
toggle — only the standard on-connect refresh burst and, over HTTPS, a generic
click-analytics event (`POST /track/event/upload` to `track-ger.aqara.com`). The
feature's own description text ("access via Apple Home will be restricted") only
makes sense as an account/cloud/bridge-level access policy — the lock firmware has
no concept of "Apple Home". Not a gap in the capture technique; don't re-attempt
via the write-opcode loop.

### "Contraseña sin conexión" (offline password) — generation is local, no BLE write

Tapping "Crear" produced a 6-digit one-time code **instantly**, with no loading
spinner and (checked against the continuously-running HCI snoop) no accompanying
BLE write — consistent with the patent's design (US11120656B2:
`trunc6(Hash(seed, hour_period))`): the app and the lock each derive the same code
independently from a shared per-lock seed, so nothing needs to be pushed to the
lock at creation time — only at actual keypad-entry time does the lock verify it
against its own computation. The remaining blocker to implement this in the
library is unchanged: obtaining the per-lock seed (app internal storage via
root/gadget, or a cloud endpoint — not yet found).

#### 2026-08-30 — live native hooking: the algorithm is NOT a standard crypto call

Attempted to catch the computation live via **native-only** Frida hooks (no
`Java.perform`, no ART touch — the same technique proven safe under SecNeo
earlier for file I/O) on the two plausible crypto surfaces, across three
separate "Crear" taps (real generated samples below):

1. **All of BoringSSL's HMAC/digest primitives** (`HMAC_Init_ex/_Update/_Final`,
   `EVP_DigestUpdate`/`EVP_DigestFinal_ex`) in the conscrypt module's
   `libcrypto.so` — the only implementation path `javax.crypto.Mac` /
   `MessageDigest` can take on Android. The hook demonstrably works (it
   captured real concurrent traffic: TLS-handshake Finished-message HMACs,
   OkHttp cache-key digests) but **zero calls correlate with the "Crear" tap**.
2. **`liblumidevsdk.so`'s own bare AES/crypto C functions**
   (`getEncryptedData`, `getDecryptedData`, `aesEncryptedContent`,
   `aesDecryptedContent` — the unwrapped internals behind the `Java_com_lumi_
   lumidevsdk_LumiDevSDK_*` JNI exports used elsewhere in the app for signing/
   encryption) — hooked live during a full "Crear" tap: **zero calls**.
3. **`libaqara_ed.so`** (another small app-private native lib, name suggestive
   of "encrypt/decrypt") — confirmed via `Process.enumerateModules()` that it
   is **never loaded** for this feature at all.

**Conclusion:** the 6-digit code is not produced by any standard Android
crypto primitive, nor by the app's own native AES/signing library. It is
almost certainly a hand-rolled arithmetic/lookup computation executed
directly inside the app's SecNeo-VM-protected Kotlin bytecode — consistent
with the `PeriodPasswordViewModel`/`CreatePeriodPasswordEntity` classes
found by static `strings` analysis of `libdatajar.so` (the "dexdata0"
catalog) earlier this session, which never resolved to any crypto helper
call site. This downgrades "find the HMAC key" to "recover an unknown
formula with no observable crypto boundary to intercept" — genuinely harder
to shortcut than the patent's `Hash(seed, period)` framing suggested.

Two real ground-truth samples were captured for future analysis (own
lock/account):

| Code | Created (local) | Expires (shown in app) |
| --- | --- | --- |
| `837246` | 2026-08-30 ~23:00:00 | 2026/08/30 23:10 |
| `079972` | 2026-08-30 23:03:53 | 2026/08/30 23:20 |

The expiry deltas (**+10 min** vs. **+~17 min**) are NOT a fixed
post-creation offset — the window likely snaps to a fixed-size grid (10 min?)
with some rounding/margin rule, itself unconfirmed with only two samples.

**Remaining paths, neither attempted this session:** (a) a Java/ART-level
hook directly on the Kotlin method that builds the code — SecNeo is known to
crash within minutes of any `Java.perform`-based hook, so this would need to
be a single surgical hook fired right before one "Crear" tap, accepting the
crash risk; (b) reversing the relevant slice of SecNeo's VMP dispatch table
statically — the approach the predecessor Codex project attempted and did
not solve for anything in this app.

#### 2026-08-30 (resolved) — the code is CLOUD-generated, not local at all

The "no BLE write = 100% local generation" assumption that anchored this
whole investigation across three sessions was **wrong** — it only ruled out
a BLE round-trip, never an HTTPS one. Captured the full HTTPS traffic (native
`SSL_read`/`SSL_write` hex dump + offline HTTP/2+HPACK reassembly — new
tools, see below) around three "Crear" taps and found the server handing
back the exact codes the app displayed:

```json
{"result":{"passwd":["956511","651399","637408","341308","234231","058138","818500","112802"]},"code":0,...}
```

`651399` and `637408` are byte-for-byte the two codes shown in the app UI at
that moment (see the samples table above) — the server pre-generates a
**batch of 8 codes per 10-minute window** and the app just pops one off the
list per "Crear" tap. A companion "history" call
(`GET /app/v1.0/lumi/dev/bluetooth/lock/passwd`'s sibling
`.../password/log/query?did=...`) confirmed the exact window math:
`startTime`/`endTime` in the responses are precisely `floor(now_ms /
600000) * 600000` boundaries (verified: `1788123600000`/`1788124200000`/
`1788124800000` are all exact multiples of `600000`) — a plain UTC-epoch-
aligned **10-minute grid**, not an hour as the patent language suggested.
The app's "Caduca" display is `endTime + 10 min` (one extra grid period of
UI-shown grace), which is what made the earlier raw samples' expiry deltas
look inconsistent — they weren't, the raw grid is exactly 10 minutes, only
the *displayed* grace window varies with how far into its own 10-min window
a code was created.

**The exact endpoint, recovered from the raw HPACK bytes despite a
mid-connection dynamic-table desync** (the `:path` pseudo-header is sent as
a literal string against a static-table name, so it survives even when
later indexed references in the same block don't resolve):

```text
GET /app/v1.0/lumi/dev/bluetooth/lock/passwd
```

— same `rpc-ger.aqara.com` host, same header/signing scheme already
implemented in `aqara_ble`'s cloud client and already proven byte-identical
to the app's own requests (specs/037-cloud-session-mitm). **No new crypto
to reverse** — this is "add one more authenticated GET call," not "find the
seed." The `did` and a couple of signing fields (timestamp, nonce/sign) ride
either as headers our client already knows how to build, or as HPACK
indexed references to values established earlier in the same connection
(not recovered byte-for-byte from this capture, but not new territory
either). Implementing this as an `aqara_ble` feature (a
`fetch_offline_passwords()`/`create_offline_password()` cloud-client method)
is real feature work, not further RE — should go through the normal
`/speckit-specify` flow rather than being hand-rolled.

**New reusable tools** (not yet promoted from scratchpad, worth keeping for
the next cloud-capture need): `sslfull.js` (native `SSL_read`/`SSL_write`
hook dumping **full hex**, tagged by the `SSL*` pointer and direction — a
cleaner rebuild of the `scratchpad/sslfull.js` mentioned in
[reverse-engineering.md](../../reverse-engineering.md) §2, which didn't
survive between sessions) and `decode_h2.py` (offline HTTP/2 frame parser +
HPACK decoder, dedups the double-hooked `SSL_write` and splits
pointer-reused connections on the client preface — same two bugs
`specs/037-cloud-session-mitm/spec.md` already documented fixing once
before). Both scripts + this method are straightforward to redo from this
write-up if the scratchpad is gone again next session.

**2026-08-31 — implemented** (`specs/038-offline-password-cloud`):
`aqara_ble.fetch_offline_passwords(device_id, auth_headers, base_url,
signer=None) -> OfflinePasswordBatch` (the current 10-minute window's
pending codes, `codes` from the server + `window_start_ms`/`window_end_ms`
derived locally from the confirmed grid) and
`aqara_ble.fetch_offline_password_log(device_id, start_time_ms, end_time_ms,
auth_headers, base_url, signer=None) -> tuple[OfflinePasswordLogEntry, ...]`
(the issuance history, all fields server-provided). Both reuse the existing
`make_local_signer`/`_request_json` machinery unchanged — no new crypto.
**Not yet confirmed byte-for-byte against hardware**: the exact wire shape
of the `passwd`-fetch request (whether `device_id` needs to ride on it at
all, and how) — `specs/038-offline-password-cloud/tasks.md` T018/T019 track
that live-capture verification pass explicitly as the one remaining step,
requiring the maintainer's phone/account.

#### 2026-08-31 — T018/T019 live verification: `did` rides as a JSON body on the GET

Fresh native SSL-hook capture (repacked app, `tools/capture_ssl_native.js` →
`ssl_capture.log`, real account/device) caught the exact `SSL_write`
immediately preceding a real `passwd` response — plaintext body:
`{"did":"matt.73cb7865154223b90e81d000"}`. So `device_id` **does** ride on
the wire, as a JSON request body on the GET (not a header, not a query
param) — the opposite of what `_request_json`'s own comment assumed ("a GET
with no payload... matches the real app, which never sends a body on its
GET-verb endpoints either" — that generalization was wrong for this one
endpoint). Also reconfirmed the 10-minute grid live: a fresh "Crear" tap
returned 8 pending codes with `startTime=1788171000000`/
`endTime=1788171600000` (exact 600000ms multiples) and the app displayed
`Caduca: 2026/08/31 12:30` (endTime + 10 min grace, as already documented).
`fetch_offline_passwords()` now sends `{"did": device_id}` as the payload;
tests updated (`test_fetch_offline_passwords_sends_did_as_a_json_body`).

### "Contraseña programada remota" — blocked on a Matter Controller prerequisite

This UI entry (distinct from "Contraseña sin conexión") requires an Aqara Matter
Controller already paired to the home ("Después de conectar al Controlador Matter
de Aqara, puedes configurar contraseñas de forma remota") — without one, the
screen only offers "Exponer" (expose/pair a controller), no password can be
created to capture. Out of scope until a Matter Controller is set up; not a BLE
opcode we can chase directly.

**2026-08-29 verification: there is no separate, standalone "Contraseña
programada".** Exhaustively enumerated every screen reachable from the lock
that isn't "Gestión de usuarios" (main lock screen fully scrolled: Contraseña
sin conexión / Gestión de usuarios / Contraseña programada remota / Registro —
4 items, confirmed bottomed-out scroll; the "..." settings menu fully scrolled:
21 items, none password-related besides the two above). The settings menu's
**"Modos de bloqueo"** screen (safe to view — not "Gestión de usuarios")
explicitly ties the two names together in its own copy: "Modo estándar ...
con soporte para desbloqueo remoto **y configuración de contraseña
programada**" (i.e. remote unlock + scheduled-password config are the same
Matter-gated bundle), versus "Modo Bluetooth: Solo admite conexiones
Bluetooth directas. Sin control remoto ni respuesta a automatismos." So
"contraseña programada" and "contraseña programada remota" are literally the
same feature, gated by Matter Controller pairing / "Modo estándar" — not by
"Gestión de usuarios", and not a second hidden opcode. This closes item 7 of
the roadmap as a genuine, verified negative result (not an assumption).
