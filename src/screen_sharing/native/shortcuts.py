"""Freedesktop launchers, recognized by Omarchy's application menu."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .profiles import Profile

ASSETS = Path(__file__).parent / "assets"


def icon_path(machine):
    if machine not in ("auto", "mac-mini", "mac-studio", "macbook", "imac", "desktop", "laptop", "server"):
        raise ValueError("Unknown machine type")
    return ASSETS / "omascreen.png"


def profile_icon(profile):
    if profile.icon_mode == "custom" and profile.icon and Path(profile.icon).is_file():
        return Path(profile.icon)
    if profile.icon_mode in ("online", "mac") and profile.fetched_icon and Path(profile.fetched_icon).is_file():
        return Path(profile.fetched_icon)
    machine = profile.detected_machine if profile.machine == "auto" else profile.machine
    if profile.icon_mode == "lucide":
        icons = {"mac-mini": "computer", "mac-studio": "computer", "macbook": "laptop",
                 "laptop": "laptop", "server": "server"}
        return ASSETS / (icons.get(machine, "monitor") + ".svg")
    return icon_path(machine or "auto")


def applications_dir():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"


def shortcut_path(profile):
    profile.validate()
    return applications_dir() / f"screen-sharing-{profile.id}.desktop"


def desktop_string(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def exec_argument(value):
    # Exec has its own quoting rules; it is not a shell command.
    value = str(value).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return desktop_string('"' + value + '"')


def refresh():
    if tool := shutil.which("update-desktop-database"):
        subprocess.run([tool, str(applications_dir())], capture_output=True, check=False)


def create(profile: Profile):
    path = shortcut_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    executable = Path(sys.executable).parent / "omascreen"
    command = " ".join(exec_argument(arg) for arg in (executable, "--app", profile.id))
    path.write_text("\n".join([
        "[Desktop Entry]", "Type=Application", "Version=1.0",
        f"Name={desktop_string(profile.name)}",
        "GenericName=Omascreen", "Comment=Open a remote desktop",
        f"Exec={command}", f"Icon={desktop_string(profile_icon(profile))}",
        "Terminal=false", "Categories=Network;RemoteAccess;",
        "Keywords=Mac;Screen Sharing;Remote Desktop;",
        f"StartupWMClass=screen-sharing-{profile.id}", "StartupNotify=false",
        "Actions=Windowed;Fullscreen;", "",
        "[Desktop Action Windowed]", "Name=Open in Window",
        f"Exec={command} --windowed", "",
        "[Desktop Action Fullscreen]", "Name=Open Fullscreen",
        f"Exec={command} --fullscreen", "",
    ]))
    path.chmod(0o644)
    refresh()
    return path


def remove(profile):
    shortcut_path(profile).unlink(missing_ok=True)
    refresh()


def create_manager():
    path = applications_dir() / "omascreen.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    executable = Path(sys.executable).parent / "omascreen"
    path.write_text("\n".join([
        "[Desktop Entry]", "Type=Application", "Name=Omascreen",
        "Comment=Connect to Macs and VNC desktops",
        f"Exec={exec_argument(executable)}",
        f"Icon={desktop_string(icon_path('auto'))}",
        "Terminal=false", "Categories=Network;RemoteAccess;",
        "Keywords=Mac;VNC;Screen Sharing;Remote Desktop;",
        "StartupWMClass=omascreen", "StartupNotify=true", "",
    ]))
    refresh()
    return path
