# Installation and packaging

## Omarchy / Arch Linux

```sh
omarchy pkg add uv git libfdk-aac portaudio vulkan-icd-loader wl-clipboard tigervnc avahi
git clone https://github.com/BuiltByTed/omascreen.git
cd omascreen
./scripts/install.sh
```

Install your GPU's appropriate Vulkan driver if one is not already present.
The system dependencies above use Omarchy's normal package installation flow.
`tigervnc` is needed for standard VNC; `avahi-browse` and local mDNS are used for
optional model detection. `wl-clipboard` supplies Wayland clipboard integration.
The Python package's media, GUI, and rendering dependencies install into a
private virtual environment.

The installer creates `~/.local/share/omascreen/venv`, symlinks `omascreen` and
`screen-sharing` into `~/.local/bin`, adds the Omascreen desktop entry, and refreshes
existing connection launchers. Add `~/.local/bin` to PATH if your shell does not
already include it. The application installer does not run as root. With no
`uv`, it falls back to `python3 -m venv` and pip.

Existing profiles and keyring entries are reused without migration. The older
`~/.local/share/screen-sharing/venv` is left intact by the installer, allowing an
older installation to be recovered if needed.

## Other Linux desktops

Install Python 3.10+, a working Vulkan driver/loader, PortAudio, GLFW runtime
support, and the appropriate clipboard utility using the distribution's package
manager. TigerVNC and Avahi are optional feature dependencies. Then run the same
source installer. Omarchy theme files are optional; other desktops use Qt's
normal appearance. macOS/Windows protocol components exist upstream, but the
Omascreen manager/install workflow is primarily tested on Omarchy Linux.

## Update

From your checkout:

```sh
git pull --ff-only
./scripts/install.sh
```

Close and reopen Omascreen and any sessions to use the update. Profiles, icons,
and keyring passwords remain outside the installed Python package.

## Uninstall

First remove any per-connection launchers you no longer want with
`omascreen shortcut 'Connection name' --remove`. Remove Omascreen's own launcher
and the two command symlinks, then remove its private virtual environment:

```sh
rm -f ~/.local/share/applications/omascreen.desktop
rm -f ~/.local/bin/omascreen ~/.local/bin/screen-sharing
rm -rf ~/.local/share/omascreen/venv
```

Adjust paths if you use XDG overrides. This leaves profiles, icons, and passwords
intact. Use `omascreen password NAME --forget` or `omascreen remove NAME` before
uninstalling if you also want saved credentials removed.

## AUR and Omarchy's package repository

The app is not yet listed in either repository. Omarchy uses Arch packages:
[AUR packages can be installed through Omarchy](https://learn.omacom.io/2/the-omarchy-manual/62/development-tools),
and accepted packages in the
[Omarchy Package Repository](https://github.com/omacom/omarchy-pkgs) become
installable with its normal package command.

The publication route is:

1. Package Omascreen and its Python dependencies in Arch PKGBUILDs. In particular,
   `wgpu`, `rendercanvas`, and the Python GLFW bindings need dependency recipes
   or an agreed packaging strategy; the source installer currently gets these
   from Python's package index.
2. Verify builds in clean Arch environments and publish the recipes to AUR.
   Only after publication would `omarchy pkg aur add omascreen` work.
3. Submit a reviewed package to `omacom/omarchy-pkgs`, including a pinned source,
   checksums, and its `.omarchy/package.json` update metadata. Acceptance and
   build approval are controlled by the Omarchy maintainers. Only after that
   would `omarchy pkg add omascreen` work.

Publishing the GitHub repository alone does not register the package in either
catalog. Until those packaging steps are completed, use the installer above.
