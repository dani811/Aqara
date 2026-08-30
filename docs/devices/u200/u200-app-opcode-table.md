# U200 opcode table — extracted directly from the app's decompiled source

Unlike everything else in [operations.md](operations.md) (reverse-engineered
byte-for-byte from live BLE captures), this table comes straight from the
app's own JavaScript source: a single object literal found in the decompiled
U200 plugin (`aqara.matter.4447_10242`, see
[rn-device-plugins.md](../../reference/rn-device-plugins.md)), 2026-08-30. It's
the app's own opcode-name→hex dictionary for the SYSTEM command family — this
is what `aqara_ble/operations_catalog.py`'s names were always meant to match
(mined from an app enum in an earlier session), now confirmed from the real
source instead of an extracted enum list.

**This is a naming/existence source, not a byte-layout source** — it confirms
an opcode is real and what the app calls it, but says nothing about the
frame's internal structure (kind byte, trailer, value encoding). Cross-check
against [operations.md](operations.md) for anything actually decoded.

## ⚠️ One important contradiction, not swept under the rug

The table says `0x18 = UN_LOCK`. But three independent isolated live
captures (2026-08-30, see [operations.md](operations.md)) show `0x18`
reproducibly encoding
the **"Retraso de alerta"** (alert-delay) setting — `18 05 0a 03 <seconds>
88 <seconds XOR 0xdf>`, with the seconds byte matching the exact UI
selection every time (60s/10s/5s) and a consistent trailer formula across
all three. The real actuator is separately, solidly confirmed as `0x74`
(`BLE_OPEN_LOCK`, in this same table). Possible explanations, none
confirmed: the label is stale/left over from refactoring; `0x18` is
overloaded and means something else in this app version/firmware; or the
constant is shared with another product line where it genuinely does mean
unlock. **Trust the live capture, not this name, for what `0x18` actually
does on this device** — but don't delete the discrepancy from the record
either.

## Full table (151 entries, SYSTEM family only)

| Opcode | Name |
| --- | --- |
| `0x01` | `SYSTEM_TIME` |
| `0x02` | `VOLUME` |
| `0x03` | `LANGUAGE` |
| `0x04` | `DOUBLE_VERIFY` |
| `0x07` | `LOCK_STATUS` |
| `0x08` | `TONGUE_STATUS` |
| `0x09` | `REPORT_TONGUE_STATUS` |
| `0x0a` | `REPORT_BATTERY` |
| `0x0b` | `REPORT_VOLUME` |
| `0x0c` | `REPORT_LANGUAGE` |
| `0x0d` | `FIRMWARE_VERSION` |
| `0x11` | `REPORT_WIFI_STATUS` |
| `0x14` | `LOCAL_SETTING` |
| `0x15` | `REPORT_LOCK_STATUS` |
| `0x16` | `TEMP_PWD` |
| `0x17` | `REPORT_TEM_PWD` |
| `0x18` | `UN_LOCK` — ⚠️ see contradiction above, live capture says alert-delay |
| `0x1a` | `LOCK_SETTING` |
| `0x1b` | `REPORT_UN_LOCK` |
| `0x1c` | `DEL_TEM_PWD` |
| `0x1d` | `REPORT_LOCK_LOG` |
| `0x1e` | `REPORT_DOOR_LOG` |
| `0x20` | `FINGER_COUNT` |
| `0x21` | `HARDWARE_VERSION` |
| `0x22` | `BIND_NFC_FLAG` |
| `0x23` | `NFC_APDU` |
| `0x24` | `APDU` |
| `0x25` | `OTA_UPGRADE` / `REQUEST_OTA_ENABLE` (both map here) |
| `0x26` | `FINGER_KEY` |
| `0x27` | `TONGUE_ENABLE` |
| `0x28` | `FINGERPRINT_ALGORITHM_PARAMS` |
| `0x29` | `LOCK_WORKING_MODE` |
| `0x2a` | `KEY_IN_STATUS` |
| `0x2b` | `REPORT_KEY_STATUS` |
| `0x2c` | `BLE_CONNECT` |
| `0x2d` | `REPORT_Mute` |
| `0x2e` | `SE_APDU` |
| `0x2f` | `HEART_PCK` |
| `0x30` | `HANDLE_DIRECTION` |
| `0x33` | `TIMEZONE_TIME` |
| `0x34` | `SET_SAFE` |
| `0x35` | `READ_SAFE` |
| `0x36` | `READ_HOME_AWAY` |
| `0x37` | `REPORT_HOME_AWAY` |
| `0x39` | `SET_HOME_AWAY` |
| `0x3a` | `QUERY_HOMEKIT_BIND_STATUS` |
| `0x3b` | `OPEN_HOMEKIT_BROADCAST` |
| `0x3c` | `SET_ELECTORNIC_LOCK` |
| `0x3f` | `CONFIG_ZIGBEE` |
| `0x41` | `SET_INFRARD_VISION` |
| `0x42` | `READ_INFRARD_VISION` |
| `0x44` | `SET_STAY_DETECTION` |
| `0x45` | `READ_STAY_DETECTION` |
| `0x46` | `SET_VIDIO_RECORD_TIME` |
| `0x47` | `READ_VIDIO_RECORD_TIME` |
| `0x48` | `SET_DOOR_BELL` |
| `0x49` | `READ_DOOR_BELL` |
| `0x4a` | `ZIGBEE_STATUS` |
| `0x4b` | `SET_TEMP_OPEN` |
| `0x4c` | `READ_TEMP_OPEN` |
| `0x4d` | `DEVICE_MTU` |
| `0x4f` | `BATTERY` |
| `0x50` | `REPORT_BATTERY_POWER` |
| `0x5b` | `READ_WIRELESS_OTA_STATUS` |
| `0x5c` | `SET_OTA_SWITCH_TIME` |
| `0x5d` | `READ_OTA_SWITCH_TIME` |
| `0x61` | `REPORT_ZIGBEE_STATUS` |
| `0x63` | `PICTURE_QUALITY_PARAMS` |
| `0x64` | `READ_PICTURE_QUALITY_PARAMS` |
| `0x68` | `READ_LOCK_LANGUAGE` — confirmed live (`68 01 68`), see operations.md |
| `0x70` | `WRITE_DOOR_BELL_PUSH_SWITCH` |
| `0x71` | `READ_DOOR_BELL_PUSH_SWITCH` |
| `0x74` | `BLE_OPEN_LOCK` — confirmed live, the real actuator |
| `0x77` | `REPORT_LITHIUM_BATTERY_STATUS` |
| `0x78` | `GET_LITHIUM_BATTERY_STATUS` |
| `0x7a` | `SET_ULTRASONIC_DISTANCE` |
| `0x7b` | `QUERY_ULTRASONIC_DISTANCE` |
| `0x7c` | `SET_DISABLE_FACE_RECOGNITION_TIME` |
| `0x7d` | `QUERY_DISABLE_FACE_RECOGNITION_TIME` |
| `0x83` | `SET_DOORLOCK_ALARM_VOLUME` — confirmed live |
| `0x84` | `QUERY_DOORLOCK_ALARM_VOLUME` — confirmed live |
| `0x8b` | `SET_MOTOR_AUTO_LOCK_AND_RELEASE_TIME_INFO` |
| `0x8c` | `QUERY_MOTOR_AUTO_LOCK_AND_RELEASE_TIME_INFO` |
| `0x8d` | `SET_MOTOR_DIRECTION_AND_TORQUE` |
| `0x8e` | `QUERY_MOTOR_DIRECTION_AND_TORQUE` |
| `0x8f` | `QUERY_WIFI_STATUS` |
| `0x93` | `SET_AWAY_HOME_STATUS` |
| `0x94` | `AWAY_HOME_STATUS` |
| `0xa2` | `QUERY_WIFI_CONFIG_STATUS` |
| `0xa3` | `SET_NO_DISTURB_MODE` |
| `0xa4` | `QUERY_NO_DISTURB_MODE` |
| `0xa7` | `DOWNGRADE_PROTECTION` |
| `0xaa` | `SET_FACE_INDENTIFY_ON_OFF` |
| `0xab` | `GET_FACE_INDENTIFY_ON_OFF` |
| `0xad` | `SET_AUTO_LOCK_TIME` — genuinely a real opcode name per the app; 3 isolated live captures never observed it fire for either auto-lock toggle/timer tested, meaning it's tied to some OTHER auto-lock action not yet isolated (not "doesn't exist" as flatly as previously stated — soften that claim) |
| `0xae` | `GET_AUTO_LOCK_TIME` |
| `0xaf` | `SET_VERIFY_FAIL_TIME` — confirmed live |
| `0xb0` | `GET_VERIFY_FAIL_TIME` |
| `0xb5` | `SET_OTHER_PLATFORM` |
| `0xb6` | `GET_OTHER_PLATFORM` |
| `0xbb` | `REPORT_MOTOR_SETTING` |
| `0xbf` | `SET_OPEN_DOOR_DIRECTION` |
| `0xc0` | `GET_OPEN_DOOR_DIRECTION` |
| `0xc3` | `GET_LOCK_VOLUME` — confirmed live |
| `0xc4` | `SET_AUXILIARY_LOCKING` — confirmed live |
| `0xc5` | `GET_AUXILIARY_LOCKING` |
| `0xc6` | `SET_NORMALLY_OPEN_MODE` |
| `0xc7` | `GET_NORMALLY_OPEN_MODE` |
| `0xc8` | `SET_NORMALLY_OPEN_MODE_PWD` |
| `0xc9` | `SET_LOCK_CALIBRATION` |
| `0xca` | `SET_ALARM_ENABLE` |
| `0xcb` | `GET_ALARM_ENABLE` |
| `0xcc` | `ANTI_LOCK_MANAGER_STATUS` |
| `0xcd` | `REPORT_ANTI_LOCK_MANAGER_STATUS` |
| `0xd5` | `SET_AUTO_LOCKUP_DELAY_TIME` — confirmed live (both timers) |
| `0xd6` | `GET_AUTO_LOCKUP_DELAY_TIME` |
| `0xd7` | `SET_ADVANCED_MODE` |
| `0xd8` | `GET_ADVANCED_MODE` |
| `0xd9` | `SET_UWB_CONFIG` |
| `0xda` | `REPORT_UWB_CONFIG` |
| `0xdb` | `REPORT_UWB_DISTANCE` |
| `0xdc` | `GET_REPORT_NORMALLY_OPEN_MODE_STATE` |
| `0xdd` | `GET_FRONT_CONNECTION` |
| `0xde` | `GET_BATTERY_INFO` |
| `0xdf` | `SET_DOOR_LOCK_TYPE` |
| `0xe0` | `GET_DOOR_LOCK_TYPE` |
| `0xe1` | `SET_LIMIT_POINT` |
| `0xe2` | `GET_LIMIT_INFO` |
| `0xe3` | `SET_PULL_SPRING` |
| `0xe4` | `GET_PULL_SPRING` |
| `0xe5` | `GET_DOOR_LOCK_STATUS` |
| `0xe6` | `REPORT_DOOR_LOCK_STATUS` |
| `0xe8` | `SET_ASSIST_TURN_SETTING` — confirmed live |
| `0xe9` | `QUERY_ASSIST_TURN_SETTING` |
| `0xea` | `SET_AND_REPORT_VOICE_OTA_STATUS` — the control-channel status/progress opcode for the language-pack OTA transfer (the bulk data itself rides a separate unencrypted characteristic, see [operations.md](operations.md#2026-08-30-resolved--the-real-mechanism-is-a-bulk-ota-file-transfer-not-a-short-control-channel-command)) |
| `0xeb` | `SET_SILENT_CONTROL_LOCK_SETTING` (our catalog: `SET_SILENT_CONTROL_LOCK`) |
| `0xec` | `QUERY_SILENT_CONTROL_LOCK_SETTING` |
| `0xed` | `SET_LOCK_WORK_MODE` |
| `0xee` | `GET_LOCK_WORK_MODE` |
| `0xef` | `SET_PASSAGE_DATA` |
| `0xf1` | `GET_PASSAGE_DATA` |
| `0xf2` | `SET_GOOGLE_VOICE_UNLOCK_STATE` |
| `0xf3` | `GET_GOOGLE_VOICE_UNLOCK_STATE` |
| `0xf4` | `REPOFT_E2E_SECRECT_KEY` (app's own typo, kept verbatim) |
| `0xf9` | `SET_UWB_ANTI_ATTACK` |
| `0xfa` | `GET_UWB_ANTI_ATTACK` |
| `0xfb` | `SET_ASSIST_TURN_ENABLE` |
| `0xfc` | `GET_ASSIST_TURN_ENABLE` |
| `0xfd` | `SET_UWB_APPROACH_DIRECTION` |
| `0xfe` | `GET_UWB_APPROACH_DIRECTION` |

## Diff against `aqara_ble/operations_catalog.py`

45 of 151 names differ from our catalog's SYSTEM-family names — almost all
are cosmetic (our catalog fixed the app's own typos, e.g. `REPORT_TEM_PWD`
→ `REPORT_TEMP_PWD`, `FACE_INDENTIFY` → `FACE_IDENTIFY`) or naming-style
differences (`QUERY_*` vs `GET_*`) that don't change meaning. A genuine,
not-yet-catalogued set: `0x1d/0x1e/0x34/0x35/0x36/0x37/0x3c/0x41/0x42/0x44/
0x45/0x46/0x47/0x63/0x64/0xdc/0xdd/0xea/0xef/0xf1` have no entry at all in
our SYSTEM family list — worth adding as `catalogued` (name-only, no frame)
in a future pass; none of them block anything currently in progress.
