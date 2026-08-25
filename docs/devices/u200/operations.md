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

### Voice / alert volume

| Preset | Serialized request (hex) — `kind|command|body|trailer` |
|--------|--------------------------------------------------------|
| `MEDIUM` | `01 d3 02d13e15 d5fddfe4` |
| `HIGH` | `01 d3 02d23e16 5faddd09` |

## Full catalog (from the app enum)

214 operations across 8 families; `confirmed` = verified live, `catalogued` = from
the enum with exact `data` unverified. The two confirmed above are `0x74`
(BLE_OPEN_LOCK) and `0x2f` (HEART_PCK); everything else is `catalogued`.

### SYSTEM (`0x01`, reply `0x81`)

| sub | name | status |
|-----|------|--------|
| `0x01` | SYSTEM_TIME | catalogued |
| `0x02` | VOLUME | catalogued |
| `0x03` | LANGUAGE | catalogued |
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
| `0x18` | UN_LOCK | catalogued |
| `0x1a` | LOCK_SETTING | catalogued |
| `0x1b` | REPORT_UN_LOCK | catalogued |
| `0x1c` | DEL_TEMP_PWD | catalogued |
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
| `0x39` | READ_AWAY_HOME_STATUS | catalogued |
| `0x3a` | HOMEKIT_BIND | catalogued |
| `0x3b` | HOMEKIT_BROADCAST | catalogued |
| `0x3f` | CONFIG_ZIGBEE | catalogued |
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
| `0xad` | SET_AUTO_LOCK_TIME | catalogued |
| `0xae` | GET_AUTO_LOCK_TIME | catalogued |
| `0xaf` | SET_VERIFY_FAIL_TIME | catalogued |
| `0xb0` | GET_VERIFY_FAIL_TIME | catalogued |
| `0xb5` | SET_OTHER_PLATFORM | catalogued |
| `0xb6` | GET_OTHER_PLATFORM | catalogued |
| `0xbb` | REPORT_MOTOR_SETTING | catalogued |
| `0xbf` | SET_OPEN_DOOR_DIRECTION | catalogued |
| `0xc0` | GET_OPEN_DOOR_DIRECTION | catalogued |
| `0xc3` | GET_LOCK_VOLUME | catalogued |
| `0xc4` | SET_AUXILIARY_LOCKING | catalogued |
| `0xc5` | GET_AUXILIARY_LOCKING | catalogued |
| `0xc6` | SET_NORMALLY_OPEN_MODE | catalogued |
| `0xc7` | GET_NORMALLY_OPEN_MODE | catalogued |
| `0xc8` | SET_NORMALLY_OPEN_MODE_PWD | catalogued |
| `0xc9` | SET_LOCK_CALIBRATION | catalogued |
| `0xca` | SET_ALARM_ENABLE | catalogued |
| `0xcb` | GET_ALARM_ENABLE | catalogued |
| `0xcc` | ANTI_LOCK_MANAGER_STATUS | catalogued |
| `0xcd` | REPORT_ANTI_LOCK_MANAGER_STATUS | catalogued |
| `0xd5` | SET_AUTO_LOCKUP_DELAY_TIME | catalogued |
| `0xd6` | GET_AUTO_LOCKUP_DELAY_TIME | catalogued |
| `0xd7` | SET_ADVANCED_MODE | catalogued |
| `0xd8` | GET_ADVANCED_MODE | catalogued |
| `0xd9` | UWB_CONFIG | catalogued |
| `0xda` | UWB_REPORT | catalogued |
| `0xdb` | UWB_DISTANCE | catalogued |
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
| `0xeb` | SET_SILENT_CONTROL_LOCK | catalogued |
| `0xec` | GET_SILENT_CONTROL_LOCK | catalogued |
| `0xed` | SET_LOCK_WORK_MODE | catalogued |
| `0xee` | GET_LOCK_WORK_MODE | catalogued |
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
