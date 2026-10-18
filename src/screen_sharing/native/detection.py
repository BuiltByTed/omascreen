"""Credential-free RFB detection and optional Bonjour/SSH Mac metadata."""
from dataclasses import dataclass
import re
import socket
import subprocess
import threading

from PySide6.QtCore import QObject, Signal


@dataclass
class Detection:
    apple: bool = False
    high_performance: bool | None = None
    model: str = ""
    machine: str = ""
    message: str = ""


def machine_for_model(model, name=""):
    # Newer model IDs no longer encode the family. Keep known IDs exact;
    # otherwise a Bonjour display name is only a family hint.
    if model in {"Mac16,10", "Mac16,11", "Mac14,3", "Mac14,12"}:
        return "mac-mini"
    if model in {"Mac13,1", "Mac13,2", "Mac14,13", "Mac14,14", "Mac15,14", "Mac16,9", "Mac17,15"}:
        return "mac-studio"
    text = (model + " " + name).lower().replace(" ", "")
    for needle, machine in [("macmini", "mac-mini"), ("macstudio", "mac-studio"),
                            ("macbook", "macbook"), ("imac", "imac"), ("xserve", "server")]:
        if needle in text:
            return machine
    return ""


def bonjour_model(host):
    """Match a resolved local RFB service, then query its device-info TXT."""
    import dns.message
    import dns.name
    import dns.query
    import dns.rdatatype
    try:
        addresses = {host.rstrip('.').lower()}
        try:
            addresses.update(item[4][0].lower() for item in socket.getaddrinfo(host, None))
        except OSError:
            pass
        result = subprocess.run(["avahi-browse", "-rtp", "_rfb._tcp"],
                                capture_output=True, text=True, timeout=3)
        for line in result.stdout.splitlines():
            fields = line.split(';')
            if len(fields) < 9 or fields[0] != '=':
                continue
            if not addresses.intersection((fields[6].rstrip('.').lower(), fields[7].lower())):
                continue
            name = re.sub(rb'\\(\d{3})', lambda m: bytes([int(m[1])]), fields[3].encode()).decode('utf-8')
            query_name = dns.name.Name([name.encode(), b'_device-info', b'_tcp', b'local', b''])
            answer = dns.query.udp(dns.message.make_query(query_name, 'TXT'), fields[7],
                                   port=5353, timeout=1, ignore_unexpected=True)
            for record in answer.answer:
                if record.rdtype == dns.rdatatype.TXT:
                    for item in record:
                        for text in item.strings:
                            if text.startswith(b'model='):
                                model = text[6:].decode('utf-8', errors='replace')
                                return model, machine_for_model(model, name)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    except Exception:
        pass  # Optional Bonjour is unavailable across most routed/VPN links.
    return '', ''


def detect(profile):
    profile.validate()
    def read_exact(sock, count):
        data = b''
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            if not chunk:
                raise OSError('The server closed the connection during detection.')
            data += chunk
        return data
    with socket.create_connection((profile.host, profile.port), timeout=3) as sock:
        banner = read_exact(sock, 12)
        if not re.fullmatch(rb'RFB \d{3}\.\d{3}\n', banner):
            raise ValueError('This port did not respond as a VNC server.')
        apple = banner == b'RFB 003.889\n'
        minor = int(banner[8:11])
        if minor >= 7:
            sock.sendall(banner if apple else b'RFB 003.008\n' if minor >= 8 else b'RFB 003.007\n')
            count = read_exact(sock, 1)[0]
            if not count:
                raise ValueError('The VNC server refused the capability probe.')
            security = read_exact(sock, count)
            apple = apple or 30 in security or 33 in security or 36 in security
        # Close BEFORE selecting authentication. No credentials are submitted.
    result = Detection(apple=apple, high_performance=None if apple else False)
    if not apple:
        result.message = 'Standard VNC server detected.'
        return result
    result.model, result.machine = bonjour_model(profile.ssh_host or profile.host)
    # The Apple auth type alone says nothing about High Performance support.
    # A trusted SSH login can establish the hardware/OS requirements.
    if profile.username:
        try:
            reply = subprocess.run(['ssh', '-oBatchMode=yes', '-oConnectTimeout=2',
                '-oStrictHostKeyChecking=yes', '-oLogLevel=ERROR', '-l', profile.username,
                '--', profile.ssh_host or profile.host,
                '/usr/bin/uname -m; /usr/bin/sw_vers -productVersion'],
                capture_output=True, text=True, timeout=4)
            parts = reply.stdout.splitlines()
            if reply.returncode == 0 and len(parts) == 2:
                result.high_performance = parts[0] == 'arm64' and int(parts[1].split('.')[0]) >= 14
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    if result.high_performance is True:
        result.message = 'Apple silicon Mac detected. High Performance hardware/OS requirements are met. Availability is confirmed when connecting.'
    elif result.high_performance is False:
        result.message = 'This Mac does not meet the High Performance requirements. Use Standard VNC.'
    else:
        result.message = 'Mac detected. High Performance support will be checked when you sign in; Standard VNC can be tried if enabled on the Mac.'
    return result


class DetectionTask(QObject):
    finished = Signal(object, str)

    def start(self, profile):
        def work():
            try:
                result, error = detect(profile), ''
            except Exception as exc:
                result, error = None, str(exc)
            try:
                self.finished.emit(result, error)
            except RuntimeError:
                pass
        threading.Thread(target=work, name='omascreen-detect', daemon=True).start()
