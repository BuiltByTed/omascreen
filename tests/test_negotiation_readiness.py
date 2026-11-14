"""Encryption setup completes on a full protocol update, without an idle wait."""
import socket
import struct

from Crypto.Cipher import AES
import pytest

from screen_sharing.proxy.protocol import negotiation
from screen_sharing.proxy.protocol.enc1103 import StreamCipher


_ECB_KEY = b"e" * 16
_CBC_KEY = b"c" * 16
_CBC_IV = b"i" * 16
_WRAPPER = AES.new(_ECB_KEY, AES.MODE_ECB)
_KEY_BLOB = b"\x00" * 4 + _WRAPPER.encrypt(_CBC_KEY) + _WRAPPER.encrypt(_CBC_IV)


def _update(*rectangles):
    data = bytearray(b"\x00\x00" + struct.pack(">H", len(rectangles)))
    for encoding, body in rectangles:
        data += struct.pack(">HHHHi", 0, 0, 0, 0, encoding)
        if encoding in (1010, 1011):
            data += struct.pack(">H", len(body))
        data += body
    return bytes(data)


class _Clock:
    now = 1000.0

    def monotonic(self):
        return self.now


class _Socket:
    def __init__(self, chunks, clock):
        self.chunks = list(chunks)
        self.clock = clock
        self.timeout = None
        self.timeouts = 0
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        if not self.chunks:
            self.clock.now += self.timeout
            self.timeouts += 1
            raise socket.timeout()
        chunk = self.chunks[0][:size]
        self.chunks[0] = self.chunks[0][size:]
        if not self.chunks[0]:
            self.chunks.pop(0)
        return chunk

    def close(self):
        self.closed = True


@pytest.fixture
def clock(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(negotiation.time, "monotonic", clock.monotonic)
    return clock


def test_ready_update_does_not_wait_for_socket_timeout(clock):
    sock = _Socket([_update((1103, _KEY_BLOB))], clock)
    cipher = negotiation._read_until_enc1103(sock, _ECB_KEY)

    assert cipher.cbc_key == _CBC_KEY
    assert sock.timeouts == 0
    assert sock.timeout == 15
    assert clock.now == 1000.0


def test_fragmented_notifications_and_multiple_updates_are_read_completely(clock):
    wire = (b"\x14" + b"\x00" * 7
            + _update((1010, b"media-description"))
            + _update((1103, _KEY_BLOB), (1011, b"later-rectangle")))
    sock = _Socket([wire[i:i + 1] for i in range(len(wire))], clock)

    assert negotiation._read_until_enc1103(sock, _ECB_KEY).cbc_key == _CBC_KEY
    assert sock.chunks == []
    assert sock.timeouts == 0


def test_pipelined_encrypted_record_stays_available_for_post_toggle_drain(clock):
    peer = StreamCipher(_KEY_BLOB, ecb_key=_ECB_KEY)
    encrypted = peer.encrypt_message(b"\x14notification")
    sock = _Socket([_update((1103, _KEY_BLOB)) + encrypted], clock)

    cipher = negotiation._read_until_enc1103(sock, _ECB_KEY)

    assert cipher._dec_ctr == 0
    assert b"".join(sock.chunks) == encrypted
    messages, consumed = cipher.decrypt_stream(sock.recv(len(encrypted)))
    assert messages == [b"\x14notification"]
    assert consumed == len(encrypted)


def test_fragmented_key_blob_keeps_full_negotiation_deadline(clock):
    sock = _Socket([_update((1103, _KEY_BLOB))[:-1]], clock)

    with pytest.raises(RuntimeError, match="did not advertise enc1103"):
        negotiation._read_until_enc1103(sock, _ECB_KEY, first_byte_timeout=10)

    assert clock.now == 1010.0
    assert sock.closed
