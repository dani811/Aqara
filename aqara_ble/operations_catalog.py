"""Catalog of every U200 BLE operation the app's command enum exposes.

Source of truth: the app's decompiled ``BleCommandConstant.ts`` (recorded in the
reverse-engineering project's ``operaciones-u200.md``). Each entry carries a
verification **status**:

- ``CONFIRMED`` — verified against the real lock (feature 009 captures).
- ``CATALOGUED`` — from the decompiled enum; the exact ``data`` is unverified.

Only open / close / keepalive are ``CONFIRMED`` today; everything else is
``CATALOGUED`` until captured live (see specs/010-operation-catalog). The status
field is the deliberate guard against the ``1f031f`` / ``200320`` failure mode,
where a decompiled name was mistaken for the real wire command.

Opcodes and frame structure are protocol, not secrets (Constitution Principle I).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandFamily(Enum):
    """First frame byte (``mainCmd``) and its reply byte (``mainCmd | 0x80``)."""

    SYSTEM = 0x01
    USER = 0x02
    LOG = 0x03
    ALARM = 0x04
    DEVICELOG = 0x05
    XXQ = 0x06
    SYSTEM_EXT = 0x07
    LONG = 0x3F

    @property
    def main_cmd(self) -> int:
        return self.value

    @property
    def reply(self) -> int:
        return self.value | 0x80


class OperationStatus(str, Enum):
    CONFIRMED = "confirmed"
    CATALOGUED = "catalogued"


@dataclass(frozen=True)
class OperationEntry:
    family: CommandFamily
    sub_cmd: int
    name: str
    status: OperationStatus = OperationStatus.CATALOGUED
    confirmed_frame: bytes | None = None
    note: str | None = None

    @property
    def key(self) -> tuple[int, int]:
        return (self.family.main_cmd, self.sub_cmd)


# --- Raw map, transcribed from the decompiled enum -------------------------
# (family, sub_cmd, name). All CATALOGUED unless promoted below.
_RAW: list[tuple[CommandFamily, int, str]] = [
    # SYSTEM (0x01) — open/close/status
    (CommandFamily.SYSTEM, 0x74, "BLE_OPEN_LOCK"),
    (CommandFamily.SYSTEM, 0x18, "UN_LOCK"),
    (CommandFamily.SYSTEM, 0x1B, "REPORT_UN_LOCK"),
    (CommandFamily.SYSTEM, 0x07, "LOCK_STATUS"),
    (CommandFamily.SYSTEM, 0x15, "REPORT_LOCK_STATUS"),
    (CommandFamily.SYSTEM, 0x08, "TONGUE_STATUS"),
    (CommandFamily.SYSTEM, 0x09, "REPORT_TONGUE_STATUS"),
    (CommandFamily.SYSTEM, 0x27, "TONGUE_ENABLE"),
    (CommandFamily.SYSTEM, 0xE5, "GET_DOOR_LOCK_STATUS"),
    (CommandFamily.SYSTEM, 0xE6, "REPORT_DOOR_LOCK_STATUS"),
    (CommandFamily.SYSTEM, 0x30, "HANDLE_DIRECTION"),
    (CommandFamily.SYSTEM, 0x2A, "KEY_IN_STATUS"),
    (CommandFamily.SYSTEM, 0x2B, "REPORT_KEY_STATUS"),
    (CommandFamily.SYSTEM, 0xCC, "ANTI_LOCK_MANAGER_STATUS"),
    (CommandFamily.SYSTEM, 0xCD, "REPORT_ANTI_LOCK_MANAGER_STATUS"),
    # SYSTEM — info / versions / battery / time
    (CommandFamily.SYSTEM, 0x0D, "FIRMWARE_VERSION"),
    (CommandFamily.SYSTEM, 0x21, "HARDWARE_VERSION"),
    (CommandFamily.SYSTEM, 0x0A, "REPORT_BATTERY"),
    (CommandFamily.SYSTEM, 0x4F, "BATTERY"),
    (CommandFamily.SYSTEM, 0x50, "REPORT_BATTERY_POWER"),
    (CommandFamily.SYSTEM, 0xDE, "GET_BATTERY_INFO"),
    (CommandFamily.SYSTEM, 0x77, "REPORT_LITHIUM_BATTERY_STATUS"),
    (CommandFamily.SYSTEM, 0x78, "GET_LITHIUM_BATTERY_STATUS"),
    (CommandFamily.SYSTEM, 0x01, "SYSTEM_TIME"),
    (CommandFamily.SYSTEM, 0x33, "TIMEZONE_TIME"),
    (CommandFamily.SYSTEM, 0x4D, "DEVICE_MTU"),
    (CommandFamily.SYSTEM, 0x2C, "BLE_CONNECT"),
    (CommandFamily.SYSTEM, 0x2F, "HEART_PCK"),
    # SYSTEM — sound / language
    (CommandFamily.SYSTEM, 0x02, "VOLUME"),
    (CommandFamily.SYSTEM, 0x0B, "REPORT_VOLUME"),
    (CommandFamily.SYSTEM, 0xC3, "GET_LOCK_VOLUME"),
    (CommandFamily.SYSTEM, 0x2D, "REPORT_MUTE"),
    (CommandFamily.SYSTEM, 0x03, "LANGUAGE"),
    (CommandFamily.SYSTEM, 0x0C, "REPORT_LANGUAGE"),
    (CommandFamily.SYSTEM, 0x68, "READ_LOCK_LANGUAGE"),
    (CommandFamily.SYSTEM, 0x83, "SET_DOORLOCK_ALARM_VOLUME"),
    (CommandFamily.SYSTEM, 0x84, "QUERY_DOORLOCK_ALARM_VOLUME"),
    # SYSTEM — auto-lock / mode / motor
    (CommandFamily.SYSTEM, 0xAD, "SET_AUTO_LOCK_TIME"),
    (CommandFamily.SYSTEM, 0xAE, "GET_AUTO_LOCK_TIME"),
    (CommandFamily.SYSTEM, 0xD5, "SET_AUTO_LOCKUP_DELAY_TIME"),
    (CommandFamily.SYSTEM, 0xD6, "GET_AUTO_LOCKUP_DELAY_TIME"),
    (CommandFamily.SYSTEM, 0xC6, "SET_NORMALLY_OPEN_MODE"),
    (CommandFamily.SYSTEM, 0xC7, "GET_NORMALLY_OPEN_MODE"),
    (CommandFamily.SYSTEM, 0xC8, "SET_NORMALLY_OPEN_MODE_PWD"),
    (CommandFamily.SYSTEM, 0x29, "LOCK_WORKING_MODE"),
    (CommandFamily.SYSTEM, 0xED, "SET_LOCK_WORK_MODE"),
    (CommandFamily.SYSTEM, 0xEE, "GET_LOCK_WORK_MODE"),
    (CommandFamily.SYSTEM, 0x8D, "SET_MOTOR_DIRECTION_AND_TORQUE"),
    (CommandFamily.SYSTEM, 0x8E, "QUERY_MOTOR_DIRECTION_AND_TORQUE"),
    (CommandFamily.SYSTEM, 0xBB, "REPORT_MOTOR_SETTING"),
    (CommandFamily.SYSTEM, 0x8B, "SET_MOTOR_AUTO_LOCK_AND_RELEASE_TIME"),
    (CommandFamily.SYSTEM, 0x8C, "QUERY_MOTOR_AUTO_LOCK_AND_RELEASE_TIME"),
    (CommandFamily.SYSTEM, 0xBF, "SET_OPEN_DOOR_DIRECTION"),
    (CommandFamily.SYSTEM, 0xC0, "GET_OPEN_DOOR_DIRECTION"),
    (CommandFamily.SYSTEM, 0xC4, "SET_AUXILIARY_LOCKING"),
    (CommandFamily.SYSTEM, 0xC5, "GET_AUXILIARY_LOCKING"),
    (CommandFamily.SYSTEM, 0xE8, "SET_ASSIST_TURN"),
    (CommandFamily.SYSTEM, 0xE9, "GET_ASSIST_TURN"),
    (CommandFamily.SYSTEM, 0xFB, "SET_ASSIST_TURN_ENABLE"),
    (CommandFamily.SYSTEM, 0xFC, "GET_ASSIST_TURN_ENABLE"),
    (CommandFamily.SYSTEM, 0xE3, "SET_PULL_SPRING"),
    (CommandFamily.SYSTEM, 0xE4, "GET_PULL_SPRING"),
    (CommandFamily.SYSTEM, 0xEB, "SET_SILENT_CONTROL_LOCK"),
    (CommandFamily.SYSTEM, 0xEC, "GET_SILENT_CONTROL_LOCK"),
    (CommandFamily.SYSTEM, 0xC9, "SET_LOCK_CALIBRATION"),
    (CommandFamily.SYSTEM, 0xDF, "SET_DOOR_LOCK_TYPE"),
    (CommandFamily.SYSTEM, 0xE0, "GET_DOOR_LOCK_TYPE"),
    (CommandFamily.SYSTEM, 0xE1, "SET_LIMIT_POINT"),
    (CommandFamily.SYSTEM, 0xE2, "GET_LIMIT_INFO"),
    # SYSTEM — alarm / security / modes
    (CommandFamily.SYSTEM, 0xCA, "SET_ALARM_ENABLE"),
    (CommandFamily.SYSTEM, 0xCB, "GET_ALARM_ENABLE"),
    (CommandFamily.SYSTEM, 0x04, "DOUBLE_VERIFY"),
    (CommandFamily.SYSTEM, 0xAF, "SET_VERIFY_FAIL_TIME"),
    (CommandFamily.SYSTEM, 0xB0, "GET_VERIFY_FAIL_TIME"),
    (CommandFamily.SYSTEM, 0xA3, "SET_NO_DISTURB_MODE"),
    (CommandFamily.SYSTEM, 0xA4, "QUERY_NO_DISTURB_MODE"),
    (CommandFamily.SYSTEM, 0x93, "SET_AWAY_HOME_STATUS"),
    (CommandFamily.SYSTEM, 0x94, "REPORT_AWAY_HOME_STATUS"),
    (CommandFamily.SYSTEM, 0x39, "READ_AWAY_HOME_STATUS"),
    (CommandFamily.SYSTEM, 0xD7, "SET_ADVANCED_MODE"),
    (CommandFamily.SYSTEM, 0xD8, "GET_ADVANCED_MODE"),
    (CommandFamily.SYSTEM, 0xA7, "DOWNGRADE_PROTECTION"),
    (CommandFamily.SYSTEM, 0x48, "SET_DOOR_BELL"),
    (CommandFamily.SYSTEM, 0x49, "READ_DOOR_BELL"),
    (CommandFamily.SYSTEM, 0x70, "SET_DOOR_BELL_PUSH_SWITCH"),
    (CommandFamily.SYSTEM, 0x71, "READ_DOOR_BELL_PUSH_SWITCH"),
    (CommandFamily.SYSTEM, 0x4B, "SET_TEMP_OPEN"),
    (CommandFamily.SYSTEM, 0x4C, "READ_TEMP_OPEN"),
    # SYSTEM — fast credentials
    (CommandFamily.SYSTEM, 0x16, "TEMP_PWD"),
    (CommandFamily.SYSTEM, 0x17, "REPORT_TEMP_PWD"),
    (CommandFamily.SYSTEM, 0x1C, "DEL_TEMP_PWD"),
    (CommandFamily.SYSTEM, 0x20, "FINGER_COUNT"),
    (CommandFamily.SYSTEM, 0x26, "FINGER_KEY"),
    (CommandFamily.SYSTEM, 0x28, "FINGERPRINT_ALGORITHM_PARAMS"),
    (CommandFamily.SYSTEM, 0x22, "BIND_NFC_FLAG"),
    (CommandFamily.SYSTEM, 0x23, "NFC_APDU"),
    (CommandFamily.SYSTEM, 0x24, "APDU"),
    (CommandFamily.SYSTEM, 0x2E, "SE_APDU"),
    # SYSTEM — OTA / connectivity / platforms
    (CommandFamily.SYSTEM, 0x25, "OTA_UPGRADE"),
    (CommandFamily.SYSTEM, 0x5C, "SET_OTA_SWITCH_TIME"),
    (CommandFamily.SYSTEM, 0x5D, "GET_OTA_SWITCH_TIME"),
    (CommandFamily.SYSTEM, 0x5B, "WIRELESS_OTA_STATUS"),
    (CommandFamily.SYSTEM, 0x11, "REPORT_WIFI_STATUS"),
    (CommandFamily.SYSTEM, 0x8F, "QUERY_WIFI_STATUS"),
    (CommandFamily.SYSTEM, 0xA2, "QUERY_WIFI_CONFIG_STATUS"),
    (CommandFamily.SYSTEM, 0x4A, "ZIGBEE_STATUS"),
    (CommandFamily.SYSTEM, 0x61, "REPORT_ZIGBEE_STATUS"),
    (CommandFamily.SYSTEM, 0x3F, "CONFIG_ZIGBEE"),
    (CommandFamily.SYSTEM, 0x3A, "HOMEKIT_BIND"),
    (CommandFamily.SYSTEM, 0x3B, "HOMEKIT_BROADCAST"),
    (CommandFamily.SYSTEM, 0xB5, "SET_OTHER_PLATFORM"),
    (CommandFamily.SYSTEM, 0xB6, "GET_OTHER_PLATFORM"),
    (CommandFamily.SYSTEM, 0xF2, "SET_GOOGLE_VOICE_UNLOCK_STATE"),
    (CommandFamily.SYSTEM, 0xF3, "GET_GOOGLE_VOICE_UNLOCK_STATE"),
    (CommandFamily.SYSTEM, 0xAA, "SET_FACE_IDENTIFY_ON_OFF"),
    (CommandFamily.SYSTEM, 0xAB, "GET_FACE_IDENTIFY_ON_OFF"),
    (CommandFamily.SYSTEM, 0xF4, "REPORT_E2E_SECRET_KEY"),
    (CommandFamily.SYSTEM, 0x14, "LOCAL_SETTING"),
    (CommandFamily.SYSTEM, 0x1A, "LOCK_SETTING"),
    (CommandFamily.SYSTEM, 0xD9, "UWB_CONFIG"),
    (CommandFamily.SYSTEM, 0xDA, "UWB_REPORT"),
    (CommandFamily.SYSTEM, 0xDB, "UWB_DISTANCE"),
    (CommandFamily.SYSTEM, 0xF9, "SET_UWB_ANTI_ATTACK"),
    (CommandFamily.SYSTEM, 0xFA, "GET_UWB_ANTI_ATTACK"),
    (CommandFamily.SYSTEM, 0xFD, "SET_UWB_APPROACH_DIRECTION"),
    (CommandFamily.SYSTEM, 0xFE, "GET_UWB_APPROACH_DIRECTION"),
    (CommandFamily.SYSTEM, 0x7A, "SET_ULTRASONIC_DISTANCE"),
    (CommandFamily.SYSTEM, 0x7B, "GET_ULTRASONIC_DISTANCE"),
    (CommandFamily.SYSTEM, 0x7C, "SET_DISABLE_FACE_RECOGNITION_TIME"),
    (CommandFamily.SYSTEM, 0x7D, "GET_DISABLE_FACE_RECOGNITION_TIME"),
    # USER (0x02)
    (CommandFamily.USER, 0x01, "ADD_USER"),
    (CommandFamily.USER, 0x02, "QUIT_ADD_USER"),
    (CommandFamily.USER, 0x11, "ADD_SUCCESS"),
    (CommandFamily.USER, 0x0C, "REPORT_ADD_USER_TIMEOUT"),
    (CommandFamily.USER, 0x03, "DEL_USER"),
    (CommandFamily.USER, 0x05, "DEL_USER_GROUP"),
    (CommandFamily.USER, 0x06, "REPORT_USER_ID"),
    (CommandFamily.USER, 0x15, "REPORT_USER_ID_NEW"),
    (CommandFamily.USER, 0x07, "FINGER_REGISTER"),
    (CommandFamily.USER, 0x08, "SET_USER_GROUP_PERMISSION"),
    (CommandFamily.USER, 0x09, "REPORT_USER_GROUP_PERMISSION"),
    (CommandFamily.USER, 0x0A, "MODIFY_USER_GROUP_ID_PERMISSION"),
    (CommandFamily.USER, 0x0B, "REPORT_USER_GROUP_ID_PERMISSION"),
    (CommandFamily.USER, 0x0D, "NFC_CID"),
    (CommandFamily.USER, 0x0E, "USER_EFFECTIVE_PERIOD"),
    (CommandFamily.USER, 0x0F, "REPORT_USER_VERIFY_VALID"),
    (CommandFamily.USER, 0x10, "MODIFY_PWD"),
    (CommandFamily.USER, 0x13, "ADD_VISITOR_PWD"),
    (CommandFamily.USER, 0x20, "ADD_VISITOR_AND_SET_VISITOR_PWD_VALID_TIME"),
    (CommandFamily.USER, 0x14, "ABORT_ADD_MIOT_USER"),
    (CommandFamily.USER, 0x18, "QUERY_ENABLE_GROUP_ID"),
    (CommandFamily.USER, 0x1A, "GET_USER_NAME_SYNC_STATUS"),
    # LOG (0x03)
    (CommandFamily.LOG, 0x01, "SYNC_USER_ID"),
    (CommandFamily.LOG, 0x14, "SYNC_USER_ID_VALID_PERIOD"),
    (CommandFamily.LOG, 0x08, "READ_TEMP_PWD"),
    (CommandFamily.LOG, 0x21, "SET_VISITOR_PWD_VALID_TIME"),
    (CommandFamily.LOG, 0x0A, "READ_DEVICE_INFO"),
    (CommandFamily.LOG, 0x0B, "NFC_CPLC"),
    (CommandFamily.LOG, 0x11, "SE_APDU"),
    (CommandFamily.LOG, 0x12, "SYNC_DOOR_LOCK_LOG"),
    (CommandFamily.LOG, 0x13, "SYNC_LOG"),
    (CommandFamily.LOG, 0x1F, "SYNC_MIOT_USER_ID_VALID"),
    (CommandFamily.LOG, 0x20, "SYNC_MIOT_CREDENTIAL_PERIOD"),
    (CommandFamily.LOG, 0x24, "GET_MORE_CREDENTIAL_INFO"),
    (CommandFamily.LOG, 0x27, "SET_USER_NAME_AND_CREDENTIAL_NAME"),
    (CommandFamily.LOG, 0x17, "WIFI_SCAN_AP"),
    (CommandFamily.LOG, 0x18, "WIFI_STATUS_QUERY"),
    (CommandFamily.LOG, 0x3E, "SET_WIFI_AP_INFO"),
    (CommandFamily.LOG, 0x75, "WIFI_ENABLE"),
    (CommandFamily.LOG, 0x76, "WIFI_SETTING"),
    (CommandFamily.LOG, 0x19, "ZIGBEE_INSTALL_CODE"),
    (CommandFamily.LOG, 0x1A, "SYNC_OTA_URL"),
    (CommandFamily.LOG, 0xA5, "VOICE_OTA_INFO_SET"),
    (CommandFamily.LOG, 0xA6, "VOICE_OTA_INFO_GET"),
    # ALARM (0x04)
    (CommandFamily.ALARM, 0x01, "ALARM"),
    (CommandFamily.ALARM, 0x02, "REMOVE_ALARM"),
    # DEVICELOG (0x05)
    (CommandFamily.DEVICELOG, 0x01, "SET_SWITCH"),
    (CommandFamily.DEVICELOG, 0x02, "GET_SWITCH"),
    (CommandFamily.DEVICELOG, 0x03, "SYNC_DEVICE_LOG"),
    (CommandFamily.DEVICELOG, 0x04, "STOP_SYNC"),
    # XXQ (0x06) — voice / indicators / sensors
    (CommandFamily.XXQ, 0x01, "SET_VOICE_AWAKE_ACTION"),
    (CommandFamily.XXQ, 0x02, "READ_VOICE_AWAKE_ACTION"),
    (CommandFamily.XXQ, 0x09, "SET_VOICE_RECOGNITION"),
    (CommandFamily.XXQ, 0x0A, "READ_VOICE_RECOGNITION"),
    (CommandFamily.XXQ, 0x03, "SET_INDICATOR_LIGHT"),
    (CommandFamily.XXQ, 0x04, "READ_INDICATOR_LIGHT"),
    (CommandFamily.XXQ, 0x05, "SET_SENSOR_MODE"),
    (CommandFamily.XXQ, 0x06, "READ_SENSOR_MODE"),
    (CommandFamily.XXQ, 0x07, "SET_SILENT_EXECUTION"),
    (CommandFamily.XXQ, 0x08, "READ_SILENT_EXECUTION"),
    (CommandFamily.XXQ, 0x0F, "SET_DIAGNOSE_SWITCH"),
    (CommandFamily.XXQ, 0x0B, "SET_GATEWAY_ADDRESS"),
    (CommandFamily.XXQ, 0x0C, "READ_GATEWAY_ADDRESS"),
    (CommandFamily.XXQ, 0x0D, "SET_ROAMING_SWITCH"),
    (CommandFamily.XXQ, 0x0E, "READ_ROAMING_SWITCH"),
    (CommandFamily.XXQ, 0xDE, "READ_BATTERY_INFO"),
    # SYSTEM_EXT (0x07) — Matter / association
    (CommandFamily.SYSTEM_EXT, 0x01, "GET_MATTER_PAIRING_CODE"),
    (CommandFamily.SYSTEM_EXT, 0x02, "GET_MATTER_LIST"),
    (CommandFamily.SYSTEM_EXT, 0x03, "REMOVE_MATTER_INFO"),
    (CommandFamily.SYSTEM_EXT, 0x04, "OPERATE_DEVICE"),
    (CommandFamily.SYSTEM_EXT, 0x05, "SET_TRAFFIC_CARD_ENABLE"),
    (CommandFamily.SYSTEM_EXT, 0x06, "GET_TRAFFIC_CARD_ENABLE"),
    (CommandFamily.SYSTEM_EXT, 0x07, "ASSOCIATE_LOCK"),
    (CommandFamily.SYSTEM_EXT, 0x08, "REPORT_ASSOCIATION_EVENT"),
    (CommandFamily.SYSTEM_EXT, 0x25, "SET_LOCK_ASSOCIATION_INFO"),
    (CommandFamily.SYSTEM_EXT, 0x26, "GET_LOCK_ASSOCIATION_INFO"),
    (CommandFamily.SYSTEM_EXT, 0x0B, "SET_AUTO_LOCK_TIME_EXT"),
    (CommandFamily.SYSTEM_EXT, 0x0C, "GET_AUTO_LOCK_TIME_EXT"),
    (CommandFamily.SYSTEM_EXT, 0x0D, "SET_MECHANICAL_UNLOCK_LINKAGE"),
    (CommandFamily.SYSTEM_EXT, 0x0E, "GET_MECHANICAL_UNLOCK_LINKAGE"),
    (CommandFamily.SYSTEM_EXT, 0x0F, "SET_FACE_RECOGNITION_PARAMS"),
    (CommandFamily.SYSTEM_EXT, 0x10, "GET_FACE_RECOGNITION_PARAMS"),
    (CommandFamily.SYSTEM_EXT, 0x11, "INDOOR_KEY_LOCK_DELAY_TIME"),
    # LONG (0x3f) — long-packet transport wrapper
    (CommandFamily.LONG, 0x00, "LONG_PACKAGE"),
]

# Entries confirmed against the real lock (feature 009). Keyed by (main, sub);
# a family can hold several confirmed frames (open vs close share sub 0x74).
_CONFIRMED: dict[tuple[int, int], tuple[bytes, str]] = {
    (0x01, 0x74): (
        bytes.fromhex("74010100b917"),
        "operate: byte1 dir (01 open / 00 close); open seq1 = 74010100b917, "
        "close seq1 = 740001003912 (see build_operate_frame)",
    ),
    (0x01, 0x2F): (bytes.fromhex("2f012f"), "keepalive / HEART_PCK sample"),
}


def _build_catalog() -> tuple[OperationEntry, ...]:
    entries: list[OperationEntry] = []
    for family, sub, name in _RAW:
        confirmed = _CONFIRMED.get((family.main_cmd, sub))
        if confirmed is not None:
            frame, note = confirmed
            entries.append(
                OperationEntry(family, sub, name, OperationStatus.CONFIRMED, frame, note)
            )
        else:
            entries.append(OperationEntry(family, sub, name))
    return tuple(entries)


OPERATIONS_CATALOG: tuple[OperationEntry, ...] = _build_catalog()


def find_operation(main_cmd: int, sub_cmd: int) -> OperationEntry | None:
    """Return the entry for a family+sub pair, or None. Never raises on unknown."""
    for entry in OPERATIONS_CATALOG:
        if entry.family.main_cmd == main_cmd and entry.sub_cmd == sub_cmd:
            return entry
    return None


def operations_in_family(main_cmd: int) -> list[OperationEntry]:
    """All catalogued operations of a family, in sub-command order."""
    return sorted(
        (e for e in OPERATIONS_CATALOG if e.family.main_cmd == main_cmd),
        key=lambda e: e.sub_cmd,
    )
