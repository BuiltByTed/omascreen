# Desktop GUI

Open **Omascreen** from the Omarchy application menu or run `omascreen` (equivalent
to `omascreen manage`). The library shows saved computers on the left. Search by
name or address, select one to see its settings, and click **Connect** or
double-click its entry. Each session opens separately, so several computers can
be connected at once.

## Add and edit connections

Choose **Add connection**, or select an existing connection and click **Edit**.

The **Connection** tab contains the name shown in menus, address, port (normally
5900), username, mode, and app-menu toggle. Enter a hostname or IP address, not a
URL. The username is your Mac account name; many standard VNC servers only need
a password, so their username can be blank.

**Detect automatically** probes the RFB greeting without submitting credentials.
A regular VNC server opens in TigerVNC. For a Mac, Omascreen offers High Performance
and Standard VNC. Apple authentication support alone is not proof of High
Performance capability: when hardware/OS information is unavailable, support
remains unknown until connection. A trusted SSH login, if already configured,
can check those requirements. The mode prompt can remember your choice; select
**Detect automatically** again in settings to reset it.

**Display & input** lets you start fullscreen and, for High Performance sessions,
choose audio, physical-display blanking, Ctrl-to-Command mapping, keyboard capture,
resolution, HiDPI scale, and codec. Defaults are windowed, audio enabled, no
blanking, and automatic display/codec settings. VNC sessions use TigerVNC's own
options for features beyond fullscreen.

## Choose an icon

Open the **Icon** tab:

| Source | How it works |
| --- | --- |
| Online Mac artwork | Detects the model with Bonjour where available and downloads matching artwork into a local cache. No File Sharing or SSH required. |
| Fetch from the Mac (SSH) | Reads the Mac's own computer icon through an existing trusted SSH key login. Requires Remote Login, not File Sharing. |
| Lucide icon | Pick a device style: monitor, laptop, desktop computer, or server. Works offline. |
| Custom image | Choose PNG, JPEG, WebP, or SVG. Omascreen saves a managed copy. |
| Omascreen icon | Uses the generated application icon. |

Use **Download icon** or **Fetch from Mac** to preview the artwork, then **Save**.
Online artwork is also fetched automatically after the first successful High
Performance connection if no cached icon is available. Some recent models are
missing from the online catalog; Omascreen keeps its app icon instead of failing
the connection. See [icon sources and details](icons.md).

Bonjour generally works on the same LAN. Across a VPN or routed network, enter
the **Mac model identifier** manually (for example `Mac13,1`), or use a reachable
local address in **SSH address** for metadata lookup. SSH mode additionally
needs a Mac username and an existing trusted key login at that address.

## Turn connections into apps

Keep **Show this connection as an app in the Omarchy menu** checked when saving.
You can also toggle it directly in the library. The entry uses the connection's
name and icon and opens that computer directly. You do not need to open the
manager first. Editing a saved connection refreshes its existing launcher.

Where supported by the launcher, its context menu includes **Open in Window**
and **Open Fullscreen**. Unchecking the app toggle removes only the launcher;
the saved connection stays in Omascreen. **Remove** deletes the connection,
launcher, and saved High Performance password after a confirmation.

## Sign in and control the session

High Performance prompts for your Mac account password. **Remember in system
keyring** saves it only after the first video frame arrives. If no supported OS
keyring is available, the option is disabled. Passwords never enter the profile
file, app launcher, or process arguments.

| High Performance shortcut | Action |
| --- | --- |
| Ctrl+Alt+Enter | Toggle fullscreen |
| Ctrl+Alt+Escape | Disconnect |
| Window close | Disconnect |

A suspended laptop or lost peer triggers a reconnect window. Omascreen retries
with increasing delays up to 15 seconds, using the active password held in memory.
**Cancel** stops retries. Authentication failure requires another sign-in.
Closing the viewer intentionally does not reconnect.

Standard VNC uses TigerVNC's password and trust prompts, controls, and reconnect
behavior. Omascreen's Mac password storage and automatic recovery do not apply
to that separate viewer. See TigerVNC's help/menu for its shortcuts.
