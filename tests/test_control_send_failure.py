"""An interrupted encrypted record must terminate TCP and request reconnect."""
import socket

from Crypto.Cipher import AES
import pytest

from screen_sharing.proxy.input import InputController
from screen_sharing.proxy.protocol.enc1103 import StreamCipher


def _cipher():
    wrapping_key = b"a" * 16
    wrapping = AES.new(wrapping_key, AES.MODE_ECB)
    blob = b"\x00" * 4 + wrapping.encrypt(b"b" * 16) + wrapping.encrypt(b"c" * 16)
    return StreamCipher(blob, ecb_key=wrapping_key)


class _PartialSend:
    def __init__(self, sock, *, shutdown_error=False):
        self.sock = sock
        self.calls = 0
        self.shutdown_calls = []
        self.shutdown_error = shutdown_error

    def sendall(self, data):
        self.calls += 1
        self.sock.sendall(data[:5])
        raise socket.timeout("interrupted after a partial encrypted record")

    def shutdown(self, how):
        self.shutdown_calls.append(how)
        if self.shutdown_error:
            raise OSError("socket already shut down")
        self.sock.shutdown(how)


def test_partial_send_shuts_down_tcp_and_rejects_further_encryption():
    cipher = _cipher()
    client, peer = socket.socketpair()
    with client, peer:
        client.settimeout(1)
        peer.settimeout(1)
        broken = _PartialSend(client)

        with pytest.raises(socket.timeout):
            cipher.encrypt_and_send(broken, b"first")

        assert broken.shutdown_calls == [socket.SHUT_RDWR]
        assert client.recv(1) == b""  # wakes Session's existing TCP receive loop
        assert len(peer.recv(1024)) == 5
        assert peer.recv(1) == b""

        with pytest.raises(ConnectionError, match="reconnect required"):
            cipher.encrypt_and_send(broken, b"second")
        with pytest.raises(ConnectionError, match="reconnect required"):
            cipher.encrypt_message(b"third")
        assert broken.calls == 1
        assert cipher._enc_ctr == 1


def test_input_stops_after_encrypted_send_failure():
    cipher = _cipher()
    client, peer = socket.socketpair()
    with client, peer:
        broken = _PartialSend(client)
        controller = InputController(broken, cipher, server_width=1920, server_height=1080)

        controller.key_event(True, ord("a"))
        controller.key_event(False, ord("a"))

        assert controller._closed
        assert controller.tx_pkts == 0
        assert broken.calls == 1
        assert broken.shutdown_calls == [socket.SHUT_RDWR]


def test_failed_shutdown_does_not_reenable_cipher_or_mask_original_send_error():
    cipher = _cipher()
    client, peer = socket.socketpair()
    with client, peer:
        broken = _PartialSend(client, shutdown_error=True)
        with pytest.raises(socket.timeout, match="partial encrypted record"):
            cipher.encrypt_and_send(broken, b"first")
        with pytest.raises(ConnectionError, match="reconnect required"):
            cipher.encrypt_and_send(broken, b"second")
        assert broken.calls == 1


def test_successful_send_retains_normal_record_roundtrip():
    sender, receiver = _cipher(), _cipher()
    client, peer = socket.socketpair()
    with client, peer:
        sender.encrypt_and_send(client, b"first")
        sender.encrypt_and_send(client, b"second")
        client.shutdown(socket.SHUT_WR)
        chunks = []
        while chunk := peer.recv(4096):
            chunks.append(chunk)
        data = b"".join(chunks)
        messages, consumed = receiver.decrypt_stream(data)
        assert messages == [b"first", b"second"]
        assert consumed == len(data)
