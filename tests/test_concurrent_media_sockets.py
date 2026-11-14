"""Concurrent Mac connections must not steal each other's UDP media ports."""
from contextlib import ExitStack
import queue
import socket
import threading
from types import SimpleNamespace

import pytest

from screen_sharing.proxy.session import Session


def test_two_peers_share_local_media_port_without_stealing_packets():
    with ExitStack() as stack:
        peers = [stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
                 for _ in range(2)]
        for peer in peers:
            peer.bind(("127.0.0.1", 0))
            peer.settimeout(0.2)
        mini = stack.enter_context(Session._bind_udp(
            "", 0, peer=peers[0].getsockname()))
        local_port = mini.getsockname()[1]
        studio = stack.enter_context(Session._bind_udp(
            "", local_port, peer=peers[1].getsockname()))
        for client in (mini, studio):
            client.settimeout(0.2)

        # Both connections use the exact same local port, as the real Macs
        # require. The peer association is what keeps their streams separate.
        assert mini.getsockname() == studio.getsockname()
        peers[0].sendto(b"mini-video", mini.getsockname())
        peers[1].sendto(b"studio-video", studio.getsockname())
        assert mini.recvfrom(1024) == (b"mini-video", peers[0].getsockname())
        assert studio.recvfrom(1024) == (b"studio-video", peers[1].getsockname())

        # Existing sendto-based firewall punches and feedback still reach the
        # correct Mac after the socket is connected.
        mini.sendto(b"mini-feedback", peers[0].getsockname())
        studio.sendto(b"studio-feedback", peers[1].getsockname())
        assert peers[0].recvfrom(1024)[0] == b"mini-feedback"
        assert peers[1].recvfrom(1024)[0] == b"studio-feedback"

        # Closing either viewer cannot interrupt the other viewer's stream.
        studio.close()
        peers[0].sendto(b"mini-after-studio-closes", mini.getsockname())
        assert mini.recvfrom(1024)[0] == b"mini-after-studio-closes"


class _EarlyRefusalSocket:
    """A connected UDP punch can receive ICMP before the server is ready."""

    def __init__(self, stop=None):
        self.calls = 0
        self.stop = stop

    def settimeout(self, value):
        pass

    def recvfrom(self, size):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionRefusedError("Mac media port is not open yet")
        if self.calls == 2:
            if self.stop is not None:
                self.stop.set()
            return b"\x80\x65media", ("127.0.0.1", 5900)
        raise socket.timeout()


@pytest.mark.parametrize("channel", ["video", "ctrl"])
def test_media_receiver_survives_early_udp_refusal(channel):
    session = Session.__new__(Session)
    session._stop_evt = threading.Event()
    sock = _EarlyRefusalSocket(session._stop_evt)
    setattr(session, f"_sock_{channel}", sock)
    packets = queue.Queue()
    setattr(session, f"_{channel}_q", packets)
    for name in ("video", "ctrl", "rtcp", "audio"):
        setattr(session, f"_rx_pkts_{name}", 0)
        setattr(session, f"_rx_bytes_{name}", 0)
    session._video_q_dropped = session._ctrl_q_dropped = 0

    getattr(session, f"_{channel}_drain_loop")()

    assert sock.calls == 2
    assert packets.get_nowait() == b"\x80\x65media"


def test_initial_burst_receiver_survives_early_udp_refusal():
    packets = []
    Session._drain_socket_into(_EarlyRefusalSocket(), packets, max_seconds=0.2)
    assert packets == [b"\x80\x65media"]
