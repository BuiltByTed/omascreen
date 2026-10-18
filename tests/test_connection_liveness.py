import threading

from screen_sharing.proxy.liveness import ConnectionLiveness
from screen_sharing.proxy.session import Session


class Clock:
    monotonic = 1000.0
    elapsed = 10000.0

    def advance(self, seconds):
        self.monotonic += seconds
        self.elapsed += seconds

    def watchdog(self):
        return ConnectionLiveness(
            monotonic=lambda: self.monotonic, elapsed=lambda: self.elapsed)


def test_linux_suspend_detected_even_if_traffic_arrives_before_next_tick():
    clock = Clock()
    watchdog = clock.watchdog()
    clock.elapsed += 600  # Linux monotonic does not advance during suspend.
    clock.advance(.5)
    watchdog.note_received()
    assert 'resumed' in watchdog.check()


def test_process_pause_detected_when_both_clocks_advance():
    clock = Clock()
    watchdog = clock.watchdog()
    clock.advance(60)
    watchdog.note_received()
    assert 'paused' in watchdog.check()


def test_static_desktop_stays_connected_with_peer_heartbeats():
    clock = Clock()
    watchdog = clock.watchdog()
    for _ in range(300):
        clock.advance(2)
        watchdog.note_received()
        assert watchdog.check() is None


def test_silent_network_failure_wakes_viewer_and_stops_workers():
    clock = Clock()
    session = Session.__new__(Session)
    session._connected = True
    session._liveness = clock.watchdog()
    session._fresh_evt = threading.Event()
    session._stop_evt = threading.Event()
    session._tx_wakeup = threading.Event()
    for _ in range(14):
        clock.advance(1)
        assert session._check_connection()
    clock.advance(1)
    assert not session._check_connection()
    assert not session.is_connected
    assert session._fresh_evt.is_set()
    assert session._stop_evt.is_set()
    assert session._tx_wakeup.is_set()


def test_brief_packet_gap_is_not_a_disconnect():
    clock = Clock()
    watchdog = clock.watchdog()
    for _ in range(14):
        clock.advance(1)
        assert watchdog.check() is None
    watchdog.note_received()
    clock.advance(2)
    assert watchdog.check() is None
