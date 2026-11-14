# Connection modes and troubleshooting

## Which mode should I use?

**High Performance** uses Omascreen's Apple protocol engine and native GPU viewer.
Apple documents Apple silicon and macOS Sonoma 14 or later as requirements for
[High Performance Screen Sharing](https://support.apple.com/guide/mac-help/mchl1883115d/mac).
A compatible Mac's settings and session capabilities still determine whether
connection succeeds. This is an independent Linux implementation, not an Apple
supported Linux client.

**Standard VNC** launches the installed
[TigerVNC viewer](https://tigervnc.org/doc/vncviewer.html). It supports generic
RFB desktops and TigerVNC's supported authentication methods. macOS account
login via Apple's proprietary authentication is not the same as a standard VNC
password: enable the Mac's VNC-viewer password option for this mode. Remote
audio, Apple virtual displays, and Omascreen's reconnect supervisor are features
of High Performance mode only.

Automatic detection reads the greeting and security types, then closes before
RFB authentication. It identifies an Apple server but never treats Apple's
authentication types as proof of High Performance. A pre-existing trusted SSH
login can establish hardware/OS requirements; otherwise the UI labels support
as unknown until sign-in. There is no silent protocol downgrade after failure.

## Frozen picture after sleep

The High Performance viewer watches decrypted peer activity and a suspend-aware
clock. After wake or a sustained connection timeout it exits with an internal
reconnect signal; the native session supervisor starts a fresh connection with
bounded backoff. It retains the active credential in memory even if you did not
choose to save it. Cancel, intentional viewer closure, authentication rejection,
and a viewer crash stop automatic retries.

Use `omascreen connect NAME` or a saved app launcher for this behavior. A direct
`omascreen session ...` has no reconnect supervisor. If a connection cannot be
restored, check that Wi-Fi/VPN connectivity has returned and the Mac is awake.

## Video corruption

Both AVC and HEVC now give retransmitted RTP packets a short reordering window
before feeding an access unit to the decoder. Unrecoverable gaps break the
reference chain and request a fresh keyframe. Lost recovery keyframes are retried
even while the remote screen is static, subject to the existing rate limit.
Corrupt decoded frames are held back so recovery leaves the last good picture
on screen. Both PyAV's `is_corrupt` flag and HEVC reference errors reported only
through libav logs are checked; some HEVC concealment does not set a frame flag.
Startup packets also wait for repair if a sequence gap is present, including
when the 16-bit sequence counter wraps; retransmissions are decoded only once.

Automatic codec selection verifies that PyAV created a hardware decoder before
offering HEVC 4:4:4. A software-decoded probe frame does not demonstrate hardware
support. Machines without working HEVC 4:4:4 acceleration use AVC automatically;
an explicit codec selection still takes precedence.

If corruption persists, note whether it happens with HEVC or AVC and whether
reconnecting clears it. Try `omascreen edit NAME --codec avc` (or `hevc`) and
collect local diagnostics by launching the connection from a terminal. Do not
share capture keys, passwords, or private clipboard data in bug reports.

## Multiple Mac connections

Each session associates its UDP media sockets with its Mac's address and port.
This lets different Macs use the required local media ports simultaneously
without a newly opened viewer taking another viewer's packets. If an older
viewer freezes when a second connection opens, close and reopen both viewers
after updating Omascreen.

## Missing icons or detection

Online catalog coverage is incomplete; see [icons](icons.md). Check local mDNS
reachability and Avahi availability. Enter a model manually across networks that
do not carry Bonjour. SSH fetching requires trusted key access and Remote Login.
An icon failure never interrupts a working High Performance session.

## Password or graphics problems

The native sign-in prompt saves passwords only in a supported OS keyring. Unlock
it or enter the password manually when unavailable. VNC credentials are handled
by TigerVNC. Confirm the account is allowed in the Mac's Screen Sharing settings.

The High Performance viewer requires working Vulkan support. Run
`omascreen --list-decoders` to inspect video decode backends. Software decode can
be used when a hardware decoder cannot initialize, but rendering still needs a
working graphics stack.
