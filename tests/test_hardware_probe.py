"""A software frame from an ignored HWAccel is not hardware capability."""
from types import SimpleNamespace

import av
import av.codec.hwaccel
import pytest

from screen_sharing.proxy.media import hwcaps
from screen_sharing.proxy.media.hevc import HevcDecoder


@pytest.mark.parametrize("hardware", [False, True])
def test_probe_checks_context_even_when_frame_is_downloaded(monkeypatch, hardware):
    frame = SimpleNamespace(format=SimpleNamespace(name="yuv444p"))
    codec = SimpleNamespace(is_hwaccel=hardware,
                            decode=lambda pkt: [frame] if pkt is not None else [])
    monkeypatch.setattr(av, "CodecContext", SimpleNamespace(create=lambda *a, **kw: codec))
    monkeypatch.setattr(av.codec.hwaccel, "HWAccel", lambda **kw: object())

    assert hwcaps._probe_one("vaapi") is hardware


def test_downloaded_hardware_frame_keeps_hardware_label():
    decoder = HevcDecoder(1, prefer_hwaccel=False)
    decoder._codec = SimpleNamespace(is_hwaccel=True)
    decoder._hw_name = "vaapi"
    decoder._hw_verified = False
    frame = av.VideoFrame(2, 2, "yuv444p")
    frame.pts = 0
    decoder._pts_to_tile[0] = 0

    decoder._publish_frame(frame)

    assert decoder.hw_accel == "vaapi"
