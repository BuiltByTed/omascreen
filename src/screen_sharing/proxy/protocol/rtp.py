"""RTP packet ordering shared by startup and the live repair buffer."""


def sort_rtp_packets(
    group: list[tuple[int, bool, bytes]],
) -> list[tuple[int, bool, bytes]]:
    """Order a short RTP group, including sequence-number wrap at 65535."""
    packets = sorted(group, key=lambda packet: packet[0])
    if len(packets) < 2 or packets[-1][0] - packets[0][0] <= 0x8000:
        return packets
    # Start after the largest circular gap, not at the numerically smallest
    # sequence: a group spanning wrap must begin with its pre-wrap packets.
    gaps = [
        ((packets[(i + 1) % len(packets)][0] - packet[0]) & 0xFFFF, i)
        for i, packet in enumerate(packets)
    ]
    _, index = max(gaps)
    start = index + 1
    return packets[start:] + packets[:start]
