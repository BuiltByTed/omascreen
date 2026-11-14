"""Startup must obey the same RTP ordering/completeness rules as live video."""
import struct
from types import SimpleNamespace

import pytest

from screen_sharing.proxy.protocol import burst
from screen_sharing.proxy import session as session_mod
from screen_sharing.proxy.session import Session, SessionConfig


_VPS = b"\x40\x01\x01"
_SPS = b"\x42\x01\x01"
_PPS = b"\x44\x01\xc0"
_IDR = b"\x28\x01\x80\x00"
_DELTA = b"\x02\x01\x80\x00"
_SSRC = 0x1234


def _packet(seq, timestamp, marker, payload):
    return (struct.pack("!BBHII", 0x80, 96 | (0x80 if marker else 0),
                        seq, timestamp, _SSRC), payload)


def _gather(monkeypatch, packets):
    groups = []

    def reassemble(payloads):
        groups.append(payloads)
        return payloads

    monkeypatch.setattr(burst, "reassemble_group", reassemble)
    decryptor = SimpleNamespace(decrypt=lambda packet: packet,
                               get_primary_ssrc_group=lambda **kw: [_SSRC])
    result = burst.gather_initial_burst(
        packets, decryptor, settle_seconds=0, min_packets=0)
    return result, groups


def test_startup_packet_order_survives_sequence_wrap(monkeypatch):
    result, groups = _gather(monkeypatch, [
        _packet(0, 100, False, _PPS),
        _packet(1, 100, True, _IDR),
        _packet(65534, 100, False, _VPS),
        _packet(65535, 100, False, _SPS),
    ])

    assert groups == [[_VPS, _SPS, _PPS, _IDR]]
    assert result.last_idr == {0: _IDR}


def test_damaged_startup_picture_waits_for_live_packet_repair(monkeypatch):
    result, groups = _gather(monkeypatch, [
        _packet(1, 100, False, _VPS),
        _packet(2, 100, False, _SPS),
        _packet(3, 100, True, _PPS),
        _packet(4, 200, False, _DELTA),
        _packet(6, 200, True, _DELTA),
    ])

    assert (_SSRC, 200) in result.burst_pending
    assert groups == [[_VPS, _SPS, _PPS]]
    assert result.tile_nalus == {}


def test_startup_retransmission_is_not_fed_twice(monkeypatch):
    result, groups = _gather(monkeypatch, [
        _packet(1, 100, False, _VPS),
        _packet(2, 100, False, _SPS),
        _packet(2, 100, False, _SPS),
        _packet(3, 100, False, _PPS),
        _packet(4, 100, True, _IDR),
    ])

    assert groups == [[_VPS, _SPS, _PPS, _IDR]]
    assert result.last_idr == {0: _IDR}


@pytest.mark.parametrize("codec", ["avc", "hevc"])
def test_completed_socket_drain_does_not_wait_for_more_packets(monkeypatch, codec):
    session = Session(SessionConfig(host="example.invalid", username="test", password="test"))
    session._dest_host = "127.0.0.1"
    session._video_codec = codec
    session._recorder = None
    negotiation = SimpleNamespace(
        keys=SimpleNamespace(audio_key_s=b"", video_key_s=b"", video_key_v=b"", audio_key_v=b""),
        video_decryptor=object(),
    )
    monkeypatch.setattr(session_mod, "create_offers", lambda **kw: (b"video", b"audio"))
    monkeypatch.setattr(session_mod, "extract_offer_ssrc", lambda *a, **kw: 1)
    monkeypatch.setattr(session_mod, "connect_and_negotiate", lambda *a, **kw: negotiation)
    for name in ("SRTPDecryptor", "SRTCPDecryptor", "SRTCPEncryptor", "SRTPEncryptor"):
        monkeypatch.setattr(session_mod, name, SimpleNamespace(from_blob=lambda *a: object()))
    monkeypatch.setattr(session, "_drain_socket_into", lambda sock, packets, **kw: packets.append(b"snapshot"))
    sentinel = object()

    def gather(packets, decryptor, **kwargs):
        assert packets == [b"snapshot"]
        assert kwargs["min_packets"] == 0
        assert kwargs["settle_seconds"] == 0
        return sentinel

    monkeypatch.setattr(session_mod, "gather_initial_burst", gather)
    assert session._negotiate_and_burst(session._config) is sentinel
