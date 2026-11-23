#!/usr/bin/env python3
"""Harmless loopback traffic, so the live monitor has something to show (candidates/BEST/bin/monitor).

Only 127.0.0.1 (or ::1) is ever contacted; nothing leaves the device.

- default: N quick non-blocking connects to ports nothing listens on, so each one is refused. A refused
  connect leaves the socket table within microseconds: a monitor sees it as a jump of the kernel's
  AttemptFails and OutRsts counters, without a port.
- --open: the same N connects go to throwaway listeners this script opens first and holds for --hold
  seconds, so the sockets are in /proc/net/tcp while they last and the ports can be counted.

Any other address is refused, and so is a port something else already uses. --repeat M adds M connects
to one port, spaced by --every seconds. Start the monitor first or together with this script: it waits
--delay seconds (default 1) so the monitor has its baseline.
"""
import argparse
import errno
import ipaddress
import json
import select
import socket
import sys
import time

HOST = "127.0.0.1"
BASE = 45900


def snmp_tcp():
    try:
        lines = open("/proc/net/snmp").read().splitlines()
    except OSError:
        return {}
    for head, values in zip(lines, lines[1:]):
        head, values = head.split(), values.split()
        if len(head) > 1 and head[0] == values[0] == "Tcp:":
            return {name: int(value) for name, value in zip(head[1:], values[1:]) if value.isdigit()}
    return {}


def free(host, port, family):
    """True when nothing is bound to this port, so a connect to it will be refused."""
    probe = socket.socket(family)
    try:
        probe.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def connect(host, port, family, timeout):
    """Non-blocking connect -> (status, socket). The socket is kept only when it connected."""
    s = socket.socket(family, socket.SOCK_STREAM)
    s.setblocking(False)
    try:
        rc = s.connect_ex((host, port))
    except OSError as e:
        rc = e.errno
    if rc not in (0, errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
        s.close()
        return _status(rc), None
    deadline = time.monotonic() + timeout
    while True:
        # A non-blocking connect makes the socket writable when it succeeds or fails; SO_ERROR says which.
        _, ready, _ = select.select([], [s], [], max(0.0, deadline - time.monotonic()))
        err = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) if ready else errno.ETIMEDOUT
        if not err:
            return "connected", s
        s.close()
        return _status(err), None


def _status(err):
    return {errno.ECONNREFUSED: "refused", errno.ETIMEDOUT: "timeout"}.get(err, f"error {err}")


def hold(listeners, clients, seconds):
    """Keep the connects open while draining the accept queues, then close the client side first."""
    accepted, deadline = [], time.monotonic() + seconds
    for srv in listeners:
        srv.setblocking(False)
    while True:
        for srv in listeners:
            try:
                accepted.append(srv.accept()[0])
            except (BlockingIOError, InterruptedError):
                pass
        if time.monotonic() >= deadline:
            break
        time.sleep(0.01)
    for s in clients + accepted + listeners:
        s.close()


def _tally(counts, status):
    counts[{"connected": "connected", "refused": "refused", "timeout": "timed_out"}.get(status, "errors")] += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ports", type=int, default=100,
                    help="ports to connect to (default 100; 150 or more gives the monitor a clear burst)")
    ap.add_argument("--base", type=int, default=BASE, help=f"first candidate port (default {BASE})")
    ap.add_argument("--open", action="store_true",
                    help="open throwaway listeners first, so the sockets stay visible in the socket table")
    ap.add_argument("--hold", type=float, default=1.5,
                    help="seconds to keep --open sockets connected (default 1.5)")
    ap.add_argument("--repeat", type=int, default=0, help="also connect M times to one port")
    ap.add_argument("--port", type=int, default=0, help="port for --repeat (default: a free one)")
    ap.add_argument("--every", type=float, default=0.25, help="seconds between repeated connects (default 0.25)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait before starting (default 1)")
    ap.add_argument("--timeout", type=float, default=0.2, help="seconds to wait for each connect (default 0.2)")
    ap.add_argument("--host", default=HOST, help=f"loopback address to use (default {HOST}); others are refused")
    a = ap.parse_args(argv)
    try:
        host = ipaddress.ip_address(a.host)
    except ValueError:
        host = None
    if host is None or not host.is_loopback:
        print(f"scan_demo: refusing {a.host!r}: this demo only contacts a loopback address (127.0.0.1 or ::1)",
              file=sys.stderr)
        return 2
    if not 1 <= a.ports <= (200 if a.open else 1000) or not 1024 <= a.base <= 65000 or not 0 <= a.repeat <= 1000 \
            or a.hold < 0.05 or a.timeout <= 0 or a.every < 0.01 or a.delay < 0 or not 0 <= a.port <= 65535:
        ap.error("--ports must be 1..1000 (1..200 with --open), --base 1024..65000, --repeat 0..1000, --port "
                 "0..65535; --hold, --timeout and --every must be positive, --delay not negative")
    host, family = str(host), socket.AF_INET6 if host.version == 6 else socket.AF_INET
    kind = "own listeners" if a.open else "closed ports"
    print(f"scan_demo: {a.ports} loopback ports from {a.base} ({kind}) on {host} in {a.delay:g} s; "
          "start candidates/BEST/bin/monitor now", file=sys.stderr)
    time.sleep(a.delay)

    result = {"mode": "open" if a.open else "closed", "host": host, "attempted": 0, "refused": 0, "connected": 0,
              "timed_out": 0, "errors": 0, "skipped_in_use": 0, "repeated": None}
    before, started = snmp_tcp(), time.monotonic()

    def attempt(port):
        result["attempted"] += 1
        status, s = connect(host, port, family, a.timeout)
        _tally(result, status)
        return status, s

    if a.open:
        listeners, clients, port = [], [], a.base
        while len(listeners) < a.ports and port <= 65535:
            srv = socket.socket(family)
            try:
                srv.bind((host, port))
                srv.listen(64)
            except OSError:
                srv.close()
                result["skipped_in_use"] += 1
            else:
                listeners.append(srv)
            port += 1
        for srv in listeners:
            status, s = attempt(srv.getsockname()[1])
            if s:
                clients.append(s)
        hold(listeners, clients, a.hold)
    else:
        port = a.base
        while result["attempted"] < a.ports and port <= 65535:
            if free(host, port, family):
                status, s = attempt(port)
                if s:  # something started listening between the check and the connect
                    s.close()
            else:
                result["skipped_in_use"] += 1
            port += 1

    if a.repeat:
        repeated = {"port": a.port, "attempted": 0, "refused": 0, "connected": 0, "timed_out": 0, "errors": 0,
                    "listener": a.open}
        srv = None
        if a.open:
            srv = socket.socket(family)
            try:
                srv.bind((host, a.port))
                srv.listen(64)
            except OSError as e:
                print(f"scan_demo: cannot listen on port {a.port}: {e.strerror}", file=sys.stderr)
                return 2
            repeated["port"] = srv.getsockname()[1]
        else:
            if not a.port:
                repeated["port"] = next((p for p in range(a.base + a.ports, 65536) if free(host, p, family)), 0)
            if not repeated["port"] or not free(host, repeated["port"], family):
                print(f"scan_demo: refusing port {a.port}: something listens there. Without --open the demo only "
                      "touches ports nobody listens on.", file=sys.stderr)
                return 2
        for i in range(a.repeat):
            if i:
                time.sleep(a.every)
            repeated["attempted"] += 1
            status, s = connect(host, repeated["port"], family, a.timeout)
            _tally(repeated, status)
            if s:
                time.sleep(0.05)
                s.close()
        if srv:
            hold([srv], [], 0)
        result["repeated"] = repeated

    after = snmp_tcp()
    result["seconds"] = round(time.monotonic() - started, 2)
    result["kernel_counters"] = {k: after[k] - before[k] for k in ("ActiveOpens", "AttemptFails", "OutRsts")
                                 if k in after and k in before}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
