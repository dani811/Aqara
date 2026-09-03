"""Unit tests for the cloud voice-pack listing/selection (pure, no network)."""
from __future__ import annotations

import json

import pytest

from aqara_ble.voice_ota import VoicePackInfo, parse_voice_list, select_voice_pack

# Shape captured live 2026-09-02 (tools/probe_voice_list.py): ``result`` is a list
# of rows; each row has ``lang``/``url`` and a ``fileInfo`` that is a JSON *string*
# encoding a list of {fileName, md5}.
_LIVE_PAYLOAD = {
    "code": 0,
    "result": [
        {
            "lang": "13",
            "url": "https://cdn.aqara.com/.../aqara.matter.4447_10242/20240611190727",
            "fileInfo": json.dumps(
                [{"fileName": "U200_FR_audio_burn.bin", "md5": "2FB6A8E43870816C3E5C3319AFD903FD"}]
            ),
        },
        {
            "lang": "2",
            "url": "https://cdn.aqara.com/.../aqara.matter.4447_10242/20240611190728",
            "fileInfo": [  # also tolerate a real list (not just a JSON string)
                {"fileName": "U200_ES_audio_burn.bin", "md5": "4220816493dad2993f04a598465f008d"}
            ],
        },
    ],
}


def test_parse_voice_list_decodes_both_fileinfo_shapes():
    rows = parse_voice_list(_LIVE_PAYLOAD)
    assert len(rows) == 2
    fr, es = rows
    assert fr == VoicePackInfo(
        lang="13",
        name="",
        file_name="U200_FR_audio_burn.bin",
        md5="2fb6a8e43870816c3e5c3319afd903fd",  # lowercased
        url="https://cdn.aqara.com/.../aqara.matter.4447_10242/20240611190727",
    )
    assert es.file_name == "U200_ES_audio_burn.bin"
    assert es.download_url.endswith("/U200_ES_audio_burn.bin")


def test_parse_voice_list_raises_on_error_code():
    with pytest.raises(RuntimeError, match="106"):
        parse_voice_list({"code": 106, "message": "Invalid sign"})


def test_parse_voice_list_tolerates_wrapped_result_and_skips_bad_rows():
    payload = {"result": {"voiceList": [
        {"lang": "1", "fileInfo": "not-json"},          # unparseable → skipped
        {"lang": "2"},                                    # no fileInfo → skipped
        {"lang": "13", "url": "u", "fileInfo": [{"fileName": "x.bin", "md5": "AA"}]},
    ]}}
    rows = parse_voice_list(payload)
    assert [r.file_name for r in rows] == ["x.bin"]


def test_select_voice_pack_matches_code_name_or_filename():
    rows = parse_voice_list(_LIVE_PAYLOAD)
    assert select_voice_pack(rows, "2").file_name == "U200_ES_audio_burn.bin"     # cloud code
    assert select_voice_pack(rows, "ES").file_name == "U200_ES_audio_burn.bin"    # filename code
    assert select_voice_pack(rows, "es").file_name == "U200_ES_audio_burn.bin"    # case-insensitive
    assert select_voice_pack(rows, "13").file_name == "U200_FR_audio_burn.bin"


def test_select_voice_pack_raises_when_missing():
    rows = parse_voice_list(_LIVE_PAYLOAD)
    with pytest.raises(LookupError, match="no voice pack"):
        select_voice_pack(rows, "ZZ")
