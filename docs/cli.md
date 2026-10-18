# CLI reference

`omascreen` and `omascreen manage` open the native manager. `omascreen --help`
shows saved-connection commands. Names containing spaces must be quoted. Commands
accept an exact name (case-insensitive) or a connection ID. `screen-sharing`
remains a compatibility alias.

## Save a connection

```sh
omascreen add 'Mac Studio' --host studio.local --user mac-user --shortcut
omascreen add 'Linux desktop' --host desktop.local --protocol vnc --port 5900 --shortcut
```

New connections default to `--protocol auto`. Other modes are `apple` (High
Performance) and `vnc` (TigerVNC). Mac usernames are required for an explicit
Apple connection; enter one before choosing High Performance in auto mode.

`add` and `edit` accept:

| Option | Values / behavior |
| --- | --- |
| `--host`, `--user`, `--port` | Remote address, account name, and port (default 5900) |
| `--rename` | Change the display name |
| `--protocol` | `auto`, `apple`, `vnc` |
| `--fullscreen`, `--windowed` | Initial window mode |
| `--audio`, `--no-audio` | Remote audio; Apple mode |
| `--curtain`, `--no-curtain` | Blank the physical remote display; Apple mode |
| `--ctrl-as-cmd`, `--no-ctrl-as-cmd` | Ctrl-to-Command mapping; Apple mode |
| `--grab-keyboard`, `--no-grab-keyboard` | Keyboard capture; Apple mode |
| `--resolution` | `auto`, `1920x1080`, `2560x1440`, `3840x2160`; Apple mode |
| `--scale` | `auto`, `on`, `off`; Apple HiDPI mode |
| `--codec` | `auto`, `hevc`, `avc`; Apple mode |
| `--icon-mode` | `online`, `mac`, `lucide`, `custom`, `app` |
| `--machine` | `auto`, `mac-mini`, `mac-studio`, `macbook`, `imac`, `desktop`, `laptop`, `server` |
| `--icon` | Import a custom image and switch to custom mode |
| `--model` | Mac model identifier for online artwork |
| `--ssh-host` | Separate SSH / local metadata address |
| `--fetch-icon`, `--no-fetch-icon` | Enable/disable automatic icon fetching after connection |
| `--shortcut` | Create an app launcher; existing launchers refresh on every edit |

```sh
omascreen edit 'Mac Studio' --rename 'Studio' --fullscreen --no-audio
omascreen edit 'Studio' --protocol auto
omascreen list
omascreen detect 'Studio'
omascreen connect 'Studio'
omascreen connect 'Studio' --windowed
```

`detect` prints the result and remembers any discovered model. It stops before
RFB authentication. Hardware/OS requirements can be checked over an existing
trusted SSH key login. Unknown High Performance support remains unknown until
sign-in; an Apple greeting alone does not establish it.

## Icons and app launchers

```sh
omascreen edit 'Studio' --icon-mode online --model 'Mac13,1'
omascreen fetch-icon 'Studio'
omascreen edit 'Studio' --icon-mode lucide --machine desktop
omascreen edit 'Studio' --icon ~/Pictures/studio.png
omascreen edit 'Studio' --icon-mode mac --ssh-host studio.local
omascreen fetch-icon 'Studio'

omascreen shortcut 'Studio'
omascreen shortcut 'Studio' --remove
omascreen remove 'Studio'
```

`fetch-icon` uses the selected online or Mac source and refreshes any existing
launcher. It does not upload artwork. `shortcut --remove` retains the profile;
`remove` deletes the profile, launcher, and saved password. The CLI executes
removal immediately. See [icon documentation](icons.md) for source availability.

## Passwords

```sh
omascreen password 'Studio'
omascreen password 'Studio' --forget
```

The first command prompts without echo and stores the password in the OS
keyring. Credentials never go in JSON, command arguments, or environment
variables. These commands manage High Performance credentials; TigerVNC manages
its own authentication for standard VNC.

## Direct High Performance sessions

```sh
omascreen session --host studio.local --user mac-user --fullscreen
omascreen session --host studio.local --user mac-user --headless --auto-quit-secs 10
omascreen session --help
omascreen --list-decoders
omascreen --version
```

Direct sessions prompt for a password in the terminal. `--password-stdin` reads
it from a pipe for automation. Avoid putting secrets literally into shell history.
Add `--verbose` for diagnostics. The direct command bypasses the native manager,
saved credentials, and reconnect supervisor; use `connect` or an app launcher
for automatic recovery.

## Storage

- Profiles: `${XDG_CONFIG_HOME:-~/.config}/screen-sharing/connections.json`.
- Cached/imported icons: `${XDG_DATA_HOME:-~/.local/share}/omascreen/icons/`.
- Desktop entries: `${XDG_DATA_HOME:-~/.local/share}/applications/`.
- Passwords: the OS keyring, under the legacy `Screen Sharing` service.

The legacy profile directory and launcher IDs intentionally remain stable so
existing connections and credentials survive the rename. Profiles and managed
icons have private file permissions. Back up the profile file separately from
your keyring; it contains no passwords.
