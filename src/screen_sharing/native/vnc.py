"""Standard RFB sessions use TigerVNC's native viewer and authentication UI."""
import shutil
import subprocess


def viewer_arguments(profile):
    profile.validate()
    viewer = shutil.which("vncviewer")
    if not viewer:
        raise RuntimeError("VNC support needs TigerVNC. Install it with: omarchy pkg add tigervnc")
    host = profile.host
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    args = [viewer, f"-FullScreen={'1' if profile.fullscreen else '0'}"]
    if profile.username:
        args += ["-UserName", profile.username]
    # Explicit ::port avoids TigerVNC interpreting 5900 as a display number.
    args += [f"{host}::{profile.port}"]
    return args


def launch(profile):
    # Passwords and TLS trust are handled by TigerVNC, never argv or a file.
    return subprocess.call(viewer_arguments(profile))
