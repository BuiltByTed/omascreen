"""Corrupt decoder output must never replace the viewer's last good picture."""
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
import pytest

from screen_sharing.proxy.media.avc import AvcDecoder
from screen_sharing.proxy.media.decode_common import _av_frame_to_tile
from screen_sharing.proxy.media.hevc import HevcDecoder
from screen_sharing.proxy.media.qsvhevc import QsvHevcDecoder


@pytest.fixture
def corrupt_frame():
    # Synthetic 64x64 random RGB (numpy seed 1), libx264 ultrafast/zerolatency,
    # yuv444p intra picture truncated to 70%. Checked in so tests only need a
    # decoder. PyAV exposes its error through is_corrupt, not frame.flags or
    # decode_error_flags. No real desktop content is used.
    data = (Path(__file__).parent / "fixtures/truncated-intra.h264").read_bytes()
    codec = av.CodecContext.create("h264", "r")
    frames = codec.decode(av.Packet(data)) + codec.decode(None)
    assert len(frames) == 1
    assert frames[0].is_corrupt
    return frames[0]


def test_real_pyav_corrupt_frame_is_detected(corrupt_frame):
    tile, had_error = _av_frame_to_tile(corrupt_frame, [None], set())
    assert tile is not None
    assert had_error


@pytest.mark.parametrize("decoder_type", [AvcDecoder, HevcDecoder])
def test_flagged_frame_is_held_and_requests_recovery(decoder_type, corrupt_frame):
    decoder = decoder_type(1, prefer_hwaccel=False)
    decoder._dpb_ready = decoder._dpb_has_idr = True
    slot = decoder._tiles[0]
    slot.raw_frame = corrupt_frame
    slot.good_count = 1

    assert decoder.get_frame(0) is None
    assert decoder.consume_fir_request() == {0}
    assert decoder.clean_counts == [0]
    # Evaluated once: a held frame must not be retried on every viewer tick.
    assert decoder.get_frame(0) is None
    assert slot.last_evaluated_count == 1


def _clean_frame(pts):
    frame = av.VideoFrame.from_ndarray(np.zeros((3, 2, 2), np.uint8), format="yuv444p")
    frame.pts = pts
    return frame


def test_hevc_log_only_concealment_holds_the_affected_tile():
    decoder = HevcDecoder(2, prefer_hwaccel=False)
    decoder._dpb_has_idr = True
    decoder._hw_verified = True

    def decode(packet):
        # FFmpeg can report a missing reference but leave is_corrupt=False.
        decoder.mark_decode_concealment("Could not find ref with POC 7")
        return [_clean_frame(packet.pts)]

    decoder._codec = SimpleNamespace(decode=decode)
    decoder._decode_one(b"\x02\x01\x80\x00", 1)

    assert decoder.good_counts == [0, 1]
    assert decoder.clean_counts == [0, 0]
    assert decoder.get_frame(1) is None
    assert decoder._gate._keyframe_required == {1}
    # Apple sends the shared HEVC recovery keyframe on the base SSRC.
    assert decoder.consume_fir_request() == {0}
    assert decoder._concealed_pts == set()

    # A healthy sibling still updates while the damaged tile is held.
    decoder._pts_to_tile[10] = 0
    decoder._publish_frame(_clean_frame(10))
    assert decoder.get_frame(0) is not None

    # Once a clean recovery picture arrives the held tile updates again.
    decoder._gate.mark_idr_observed(1)
    decoder._pts_to_tile[11] = 1
    decoder._publish_frame(_clean_frame(11))
    assert decoder.get_frame(1) is not None


def test_hevc_buffered_frame_keeps_its_own_concealment_state():
    decoder = HevcDecoder(2, prefer_hwaccel=False)
    decoder._dpb_has_idr = True
    decoder._hw_verified = True
    decoder._pts_to_tile.update({1: 0, 2: 1})
    decoder._decoding_pts = 2
    decoder.mark_decode_concealment("Could not find ref with POC 7")
    decoder._decoding_pts = None

    # An earlier healthy frame emerges first; the error belongs to PTS 2.
    decoder._publish_frame(_clean_frame(1))
    assert decoder.get_frame(0) is not None
    decoder._publish_frame(_clean_frame(2))
    assert decoder.get_frame(1) is None
    assert decoder.clean_counts == [1, 0]


def test_qsv_corrupt_output_does_not_reach_renderer(corrupt_frame):
    decoder = QsvHevcDecoder(1)
    corrupt_frame.pts = 0
    decoder._pts_to_tile[0] = 0
    decoder._publish_frame(corrupt_frame)

    assert decoder.get_frame(0) is None
    assert decoder.consume_fir_request() == {0}
    assert decoder.clean_counts == [0]
