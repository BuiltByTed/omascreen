"""Fetch the remote Mac's own computer icon over an existing trusted SSH login.

Apple artwork stays in the user's private cache; it is never bundled in the app.
"""
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import threading
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal


# NSImageNameComputer lets macOS pick its actual model/color automatically.
# This is a read-only AppKit request; no remote files or settings are changed.
MAC_ICON_SCRIPT = """ObjC.import('AppKit');
var icon = $.NSImage.imageNamed($.NSImageNameComputer);
var bitmap = $.NSBitmapImageRep.imageRepWithData(icon.TIFFRepresentation);
var png = bitmap.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $.NSDictionary.dictionary);
ObjC.unwrap(png.base64EncodedStringWithOptions(0));"""


def icons_dir():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "omascreen/icons"


def fetch_mac_icon(profile):
    profile.validate()
    if not profile.username:
        raise ValueError("Enter your Mac username to fetch its icon over SSH.")
    host = profile.ssh_host or profile.host
    try:
        result = subprocess.run([
            "ssh", "-oBatchMode=yes", "-oConnectTimeout=4",
            "-oStrictHostKeyChecking=yes", "-oLogLevel=ERROR",
            "-l", profile.username, "--", host,
            "/usr/bin/osascript -l JavaScript -e " + shlex.quote(MAC_ICON_SCRIPT),
        ], capture_output=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Could not reach the Mac over SSH. Enable Remote Login and set up SSH key access.") from error
    if result.returncode:
        raise RuntimeError(
            "Could not fetch the Mac icon. Enable Remote Login on the Mac, then establish "
            "a trusted SSH key login from this computer. You can set a separate SSH address "
            "in the connection's settings.")
    try:
        image = base64.b64decode(result.stdout.strip(), validate=True)
    except ValueError as error:
        raise RuntimeError("The Mac returned an invalid icon.") from error
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 8 * 1024 * 1024:
        raise RuntimeError("The Mac returned an invalid icon.")
    return save_png(profile.id + '-mac', image)


def save_png(name, image):
    from PySide6.QtGui import QImage
    if len(image) > 8 * 1024 * 1024 or not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('The icon is not a supported PNG image.')
    decoded = QImage.fromData(image, 'PNG')
    if decoded.isNull() or max(decoded.width(), decoded.height()) > 4096:
        raise ValueError('The icon is invalid or too large (maximum 4096 pixels).')
    folder = icons_dir()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = folder / f"{name}.png"
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=".icon-")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(image)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(destination)


def online_icon_url(profile):
    catalog = json.loads((Path(__file__).parent / 'assets/device-catalog.json').read_text())
    model = profile.detected_model
    filename = catalog['models'].get(model)
    # These Studio generations share the same enclosure. The catalog predates
    # their identifiers, but has the matching Studio artwork.
    if not filename and model in {'Mac14,13', 'Mac14,14', 'Mac15,14', 'Mac16,9', 'Mac17,15'}:
        filename = 'com.apple.macstudio.icns.png'
    if not filename:
        raise ValueError('No online icon matches this model yet. Choose a custom or Lucide icon, '
                         'or fetch the exact icon from the Mac over SSH.')
    return ('https://raw.githubusercontent.com/callumgare/macos-device-icons/'
            + catalog['revision'] + '/images/' + filename)


def fetch_online_icon(profile):
    profile.validate()
    if not profile.detected_model:
        from .detection import bonjour_model
        profile.detected_model, profile.detected_machine = bonjour_model(profile.ssh_host or profile.host)
    url = online_icon_url(profile)
    request = Request(url, headers={'User-Agent': 'Omascreen/0.3'})
    with urlopen(request, timeout=8) as response:
        image = response.read(8 * 1024 * 1024 + 1)
    return save_png(profile.id + '-online', image)


def fetch_icon(profile):
    return fetch_mac_icon(profile) if profile.icon_mode == 'mac' else fetch_online_icon(profile)


def import_icon(profile, path):
    """Copy a selected image into managed storage, normalized to PNG."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QGuiApplication, QImageReader
    # SVG text needs a font database even when importing through a headless CLI.
    application = QGuiApplication.instance() or QGuiApplication(['omascreen', '-platform', 'offscreen'])
    profile.validate()
    reader = QImageReader(str(path))
    size = reader.size()
    if size.width() > 4096 or size.height() > 4096:
        raise ValueError('Choose an image no larger than 4096 × 4096 pixels.')
    image = reader.read()
    if image.isNull():
        raise ValueError('Could not read this image. Choose PNG, JPEG, WebP or SVG.')
    image = image.scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return save_png(profile.id + '-custom', bytes(data))


class IconFetch(QObject):
    finished = Signal(str, str)

    def start(self, profile):
        def work():
            try:
                path, error = fetch_icon(profile), ""
            except Exception as exc:
                path, error = "", str(exc)
            try:
                self.finished.emit(path, error)
            except RuntimeError:
                pass  # dialog was closed while the bounded SSH request ran
        threading.Thread(target=work, name="omascreen-icon", daemon=True).start()
