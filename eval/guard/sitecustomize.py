"""Offline guard loaded into every candidate Python process by bin/eval (via PYTHONPATH).

- Blocks non-loopback network connects/DNS and logs the attempt to $HC_GUARD_LOG.
- Blocks reads of hidden evaluation data ($HC_GUARD_DENY_PATHS, colon-separated prefixes).
This is a proxy for "fully offline"; the real proof is airplane mode on the demo device.
"""
import builtins
import io
import os
import socket

_LOG = os.environ.get("HC_GUARD_LOG")
_DENY = tuple(p for p in os.environ.get("HC_GUARD_DENY_PATHS", "").split(":") if p)
_open = builtins.open
_os_open = os.open


def _log(msg):
    if _LOG:
        try:
            with _open(_LOG, "a") as f:
                f.write(f"{os.getpid()} {msg}\n")
        except OSError:
            pass


def _local(host):
    h = host.decode() if isinstance(host, bytes) else str(host)
    return h in ("localhost", "::1", "", "0.0.0.0") or h.startswith("127.")


def _addr_ok(sock, addr):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return True
    return _local(addr[0])


_connect, _connect_ex, _sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto


def connect(self, addr):
    if not _addr_ok(self, addr):
        _log(f"NET blocked connect {addr!r}")
        raise OSError(101, "network disabled by offline guard")
    return _connect(self, addr)


def connect_ex(self, addr):
    if not _addr_ok(self, addr):
        _log(f"NET blocked connect_ex {addr!r}")
        return 101
    return _connect_ex(self, addr)


def sendto(self, data, *args):
    addr = args[-1]
    if not _addr_ok(self, addr):
        _log(f"NET blocked sendto {addr!r}")
        raise OSError(101, "network disabled by offline guard")
    return _sendto(self, data, *args)


_gai = socket.getaddrinfo


def getaddrinfo(host, *a, **k):
    if host is not None and not _local(host):
        _log(f"NET blocked dns {host!r}")
        raise socket.gaierror(-2, "name resolution disabled by offline guard")
    return _gai(host, *a, **k)


socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
socket.getaddrinfo = getaddrinfo


def _denied(path):
    if not _DENY or isinstance(path, int):
        return False
    try:
        p = os.path.realpath(os.fsdecode(path))
    except (TypeError, ValueError):
        return False
    return p.startswith(_DENY)


def guarded_open(file, *a, **k):
    if _denied(file):
        _log(f"FILE blocked open {file!r}")
        raise PermissionError(13, "hidden evaluation data is off-limits", str(file))
    return _open(file, *a, **k)


def guarded_os_open(path, *a, **k):
    if _denied(path):
        _log(f"FILE blocked os.open {path!r}")
        raise PermissionError(13, "hidden evaluation data is off-limits", str(path))
    return _os_open(path, *a, **k)


builtins.open = guarded_open
io.open = guarded_open
os.open = guarded_os_open
