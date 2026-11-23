"""Live connection monitor: the kernel's socket table and TCP counters, with no root and no packets.

The sampler reads /proc/net/tcp, /proc/net/tcp6 and /proc/net/snmp every half second for one window.
`summarise` turns those samples into findings and one plain sentence that the existing flow rules
(rules.FLOW_RULES) understand, so the verdict comes from the detector a pasted description gets:
detect.classify_any("flow", description).

What a window can and cannot show:

- Each sample is a snapshot. Sockets that outlive the interval appear: open sessions, half-open ones,
  connects still waiting for a reply, and time-wait leftovers of up to a minute. A connect that is
  refused, or a connection that finishes between two samples, is in no snapshot at all.
- The kernel counters cover the whole device but carry no address or port. They are the only trace of
  short-lived attempts, so a burst of refused connects is reported without naming its targets.
- No payload is read. The table lists every TCP socket of this network namespace, whichever user owns
  it; sockets in other namespaces (containers) are not visible from here.
"""
import argparse
import ipaddress
import json
import math
import socket
import sys
import tempfile
import time
from collections import Counter, namedtuple
from pathlib import Path
from typing import NamedTuple

Proc = namedtuple("Proc", "tcp tcp6 snmp")
PROC = Proc("/proc/net/tcp", "/proc/net/tcp6", "/proc/net/snmp")
INTERVAL = 0.5
COUNTERS = ("ActiveOpens", "PassiveOpens", "AttemptFails", "EstabResets", "OutRsts", "InErrs", "RetransSegs")
STATES = {"01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV", "04": "FIN_WAIT1", "05": "FIN_WAIT2",
          "06": "TIME_WAIT", "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK", "0A": "LISTEN",
          "0B": "CLOSING", "0C": "SYN_RECV"}  # 0C (NEW_SYN_RECV) is half-open too
LOGIN_PORTS = {22: "ssh", 23: "telnet", 3389: "rdp", 21: "ftp"}
# Thresholds for one window, calibrated on a desktop whose own applications fail about two connects a
# second and send about three resets a second. Below them a pattern stays in the "counters" and
# "socket_table" numbers of the JSON and does not become a finding.
PORT_SCAN_MIN_PORTS, PORT_SCAN_PER_SEC = 12, 1.2   # target ports opened on one peer during the window
PORT_SCAN_LEFTOVER_PORTS = 40         # target ports listed on one peer, some opened before the window
LOGIN_REPEAT_MIN, LOGIN_REPEAT_PER_SEC = 8, 0.8    # new connections to one login port, per peer
HALF_OPEN_MIN = 40                    # half-open sockets on one port
PERIODIC_MIN = 4                      # new connections to one remote endpoint, evenly spaced
FAILED_PER_SEC, FAILED_MIN = 10.0, 100         # kernel AttemptFails
RESETS_PER_SEC, RESETS_MIN = 20.0, 200         # kernel OutRsts
HOSTS_PER_SEC, HOSTS_MIN = 3.0, 30             # new connections from many peers to one remote port
RANK = {"login_port_repeats": 0, "half_open": 1, "port_scan": 2, "periodic": 3, "failed_connects": 4,
        "resets_sent": 5, "many_hosts": 6}


class Socket(NamedTuple):
    local: str
    local_port: int
    remote: str
    remote_port: int
    state: str = "ESTABLISHED"

    @property
    def key(self):
        return self[:4]


Sample = namedtuple("Sample", "t sockets counters")


class MonitorError(Exception):
    """The host cannot be sampled (not Linux, or /proc/net is not readable)."""


def _address(field):
    """'0100007F:0CEA' -> ('127.0.0.1', 3306). The kernel prints each 32-bit word little-endian."""
    addr, _, port = field.rpartition(":")
    try:
        raw, n = bytes.fromhex(addr), int(port, 16)
    except ValueError:
        return None
    if len(raw) == 4:
        return socket.inet_ntop(socket.AF_INET, raw[::-1]), n
    if len(raw) == 16:
        words = b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
        ip = ipaddress.IPv6Address(words)
        return str(ip.ipv4_mapped or ip), n
    return None


def parse_socktab(text):
    """Sockets listed by /proc/net/tcp or /proc/net/tcp6. Malformed lines are skipped."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4 or "local_address" in parts:
            continue
        local, remote = _address(parts[1]), _address(parts[2])
        if local and remote:
            out.append(Socket(local[0], local[1], remote[0], remote[1], STATES.get(parts[3].upper(), "OTHER")))
    return tuple(out)


def parse_snmp(text, proto="Tcp"):
    """One protocol block of /proc/net/snmp as {counter: value}; {} when the block is absent."""
    lines = text.splitlines()
    for head, values in zip(lines, lines[1:]):
        head, values = head.split(), values.split()
        if len(head) > 1 and len(values) > 1 and head[0] == values[0] == proto + ":":
            out = {}
            for name, value in zip(head[1:], values[1:]):
                try:
                    out[name] = int(value)
                except ValueError:
                    pass
            return out
    return {}


def counter_deltas(first, last):
    """({counter: delta}, note). The deltas are None, with a note, when they cannot be trusted."""
    if not first or not last:
        return None, "kernel TCP counters unavailable (/proc/net/snmp not readable or has no Tcp block)"
    out = {}
    for name in COUNTERS:
        if name not in first or name not in last:
            return None, f"counter {name} missing from /proc/net/snmp; deltas omitted"
        if last[name] < first[name]:
            return None, "kernel counters went backwards during the window (reset); deltas omitted"
        out[name] = last[name] - first[name]
    return out, None


def _is_loopback(ip):
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _duration(window):
    w = f"{window:.0f}" if abs(window - round(window)) < 0.05 else f"{window:.1f}"
    return f"{w} second" + ("" if w == "1" else "s")


def _within(window):
    return f"within {_duration(window)}"


def _outcome(states):
    """The most telling state a sampled socket was seen in."""
    for name in ("ESTABLISHED", "SYN_SENT", "SYN_RECV", "TIME_WAIT"):
        if name in states:
            return name
    return "OTHER"


def _scan_mix(outcomes):
    """How the sockets behind a port-scan finding looked when they were sampled."""
    total = sum(outcomes.values())
    only = next(iter(outcomes.items()))
    if len(outcomes) == 1 and only[1] == total:
        return {"ESTABLISHED": "all established when sampled", "SYN_SENT": "all still waiting for a reply",
                "SYN_RECV": "all half-open", "TIME_WAIT": "all already closed (in time-wait)"}.get(
            only[0], "all in another state")
    words = {"ESTABLISHED": "established", "SYN_RECV": "half-open", "SYN_SENT": "still waiting for a reply",
             "TIME_WAIT": "already closed (in time-wait)", "OTHER": "in another state"}
    return ", ".join(f"{n} {words[k]}" for k, n in outcomes.most_common())


def summarise(samples):
    """Findings, counter deltas and one description for a window of samples (pure)."""
    if len(samples) < 2:
        raise ValueError("a window needs at least two samples")
    window = samples[-1].t - samples[0].t
    within = _within(window)
    seen = {}  # socket key -> [inbound, first sample it was in, Counter(states sampled in)]
    for idx, smp in enumerate(samples):
        listening = {s.local_port for s in smp.sockets if s.state == "LISTEN"}
        for s in smp.sockets:
            if s.state == "LISTEN" or (s.remote_port == 0 and s.remote in ("0.0.0.0", "::")):
                continue
            rec = seen.get(s.key)
            if rec is None:
                # This end is the server when something listens on its port, or when it holds a
                # privileged port and the peer an ephemeral one. Every other socket counts as outgoing.
                rec = seen[s.key] = [s.local_port in listening or s.local_port < 1024 <= s.remote_port, idx,
                                     Counter()]
            rec[2][s.state] += 1

    peers, targets, half_open, firsts = {}, {}, {}, {}
    for key, (inbound, first, states) in seen.items():
        local, lport, remote, rport = key
        peer, port = (remote, lport) if inbound else (remote, rport)
        outcome = _outcome(states)
        p = peers.setdefault((inbound, peer), {"ports": set(), "new_ports": set(), "new": 0,
                                               "outcomes": Counter(), "new_outcomes": Counter()})
        p["ports"].add(port)
        p["outcomes"][outcome] += 1
        if first:  # not in the first sample, so it opened during the window
            p["new"] += 1
            p["new_ports"].add(port)
            p["new_outcomes"][outcome] += 1
            t = targets.setdefault((inbound, peer, port), {"new": 0, "locals": Counter()})
            t["new"] += 1
            t["locals"][local] += 1
            if not inbound and not _is_loopback(peer):
                firsts.setdefault((peer, port), []).append(samples[first].t)
        if inbound and "SYN_RECV" in states:
            half_open.setdefault(("in", lport, None), set()).add(key)
        elif not inbound and outcome == "SYN_SENT":
            half_open.setdefault(("out", peer, rport), set()).add(key)
    new_total = sum(p["new"] for p in peers.values())

    findings = []

    def add(kind, severity, count, sentence, **detail):
        findings.append(dict(kind=kind, severity=severity, count=count, sentence=sentence, **detail))

    # Repeated new connections to a login port, from one peer or made by this device to one peer.
    need = max(LOGIN_REPEAT_MIN, LOGIN_REPEAT_PER_SEC * window)
    busy = {(inbound, peer, port): t for (inbound, peer, port), t in targets.items()
            if port in LOGIN_PORTS and t["new"] >= need}
    for (inbound, peer, port), t in sorted(busy.items(), key=lambda kv: (-kv[1]["new"], kv[0])):
        if inbound and _is_loopback(peer) and (False, peer, port) in busy:
            continue  # loopback: both ends are this device, the outgoing sentence says it once
        service, local, n = LOGIN_PORTS[port], t["locals"].most_common(1)[0][0], t["new"]
        tail = f"{within}, consistent with repeated {service} login attempts"
        if inbound:
            target = f"to {service} port {port}" + (f" on {local}" if local not in ("0.0.0.0", "::") else "")
            origin = "from a local process" if _is_loopback(peer) else f"from {peer}"
            sentence = f"{n} new connections {target} {origin} {tail}"
        else:
            sentence = f"{n} new connections from this device to {service} port {port} on {peer} {tail}"
        add("login_port_repeats", "high", n, sentence, peer=peer, port=port, direction="in" if inbound else "out",
            note="the socket table shows connections, not whether a login succeeded")

    # Half-open sockets piled on one port: handshakes that are not completing.
    for (direction, port, remote), keys in sorted(half_open.items(), key=lambda kv: -len(kv[1])):
        if len(keys) < HALF_OPEN_MIN:
            continue
        n = len(keys)
        sentence = (f"{n} half-open connections waiting on port {port} {within}" if direction == "in" else
                    f"{n} half-open connections from this device waiting on {remote} port {port} {within}")
        add("half_open", "high", n, sentence, direction=direction, port=port,
            peers=sorted({key[2] for key in keys})[:3])

    # Many target ports on one peer: a port scan as the socket table shows it. Ports opened in the
    # window count against a lower bar than sockets already listed when the window began, which can be
    # time-wait leftovers of a scan that ended up to a minute earlier.
    need = max(PORT_SCAN_MIN_PORTS, PORT_SCAN_PER_SEC * window)
    scanned = {(inbound, peer): p for (inbound, peer), p in peers.items()
               if len(p["new_ports"]) >= need or len(p["ports"]) >= PORT_SCAN_LEFTOVER_PORTS}
    for (inbound, peer), p in sorted(scanned.items(), key=lambda kv: (-len(kv[1]["new_ports"]), kv[0])):
        if inbound and _is_loopback(peer) and (False, peer) in scanned:
            continue  # loopback: both ends are this device, the outgoing sentence says it once
        fresh = len(p["new_ports"]) >= need
        n, mix = (len(p["new_ports"]), _scan_mix(p["new_outcomes"])) if fresh else \
            (len(p["ports"]), _scan_mix(p["outcomes"]))
        head = (f"incoming tcp connections from {peer} to {n} different ports on this device" if inbound
                else f"tcp connections to {n} different ports on {peer}")
        when = within if fresh else f"during {_duration(window)} of sampling"
        sentence = f"{head} {when}, {mix}" + ("" if fresh else ", some opened before the window")
        add("port_scan", "high", n, sentence, peer=peer, direction="in" if inbound else "out",
            target_ports=(sorted(p["new_ports"]) + sorted(p["ports"] - p["new_ports"]))[:50],
            opened_in_window=len(p["new_ports"]),
            note="a sampled socket can sit in time-wait for a minute after it closed")

    # New connections to one remote endpoint at even spacing: beacon-like.
    spacing = samples[1].t - samples[0].t
    for (peer, port), times in sorted(firsts.items(), key=lambda kv: -len(kv[1])):
        gaps = [b - a for a, b in zip(times, times[1:])]
        if len(times) < PERIODIC_MIN:
            continue
        mean = (times[-1] - times[0]) / (len(times) - 1)
        if mean >= 2 * spacing and max(gaps) - min(gaps) <= max(1.5 * spacing, 0.3 * mean):
            add("periodic", "high", len(times),
                f"{len(times)} new connections to {peer} port {port} {within} at regular intervals of about "
                f"{mean:.1f} seconds", peer=peer, port=port, mean_gap_seconds=round(mean, 2))

    deltas, note = counter_deltas(samples[0].counters, samples[-1].counters)
    if deltas:
        fails, resets = deltas["AttemptFails"], deltas["OutRsts"]
        hot_f = fails >= max(FAILED_MIN, FAILED_PER_SEC * window)
        hot_r = resets >= max(RESETS_MIN, RESETS_PER_SEC * window)
        if hot_f or hot_r:
            parts = ([f"{fails} connection attempts failed (refused or timed out)"] if hot_f else []) + (
                [f"{resets} reset packets were sent by this device"] if hot_r else [])
            sentence = "kernel counters: " + " and ".join(parts) + f" {within}"
            if hot_f and new_total * 10 <= fails:
                sentence += "; sampling caught too few of them to name a target address or port"
            add("failed_connects" if hot_f else "resets_sent", "medium", fails if hot_f else resets, sentence,
                failed=fails, resets_sent=resets)

    # Many peers on one remote port: the shape of a worm or a peer-to-peer client. No rule covers it.
    by_port = {}
    for (inbound, peer), p in peers.items():
        if not inbound and p["new"]:
            for port in p["new_ports"]:
                by_port.setdefault(port, set()).add(peer)
    for port, hosts in sorted(by_port.items(), key=lambda kv: -len(kv[1]))[:1]:
        if len(hosts) >= max(HOSTS_MIN, HOSTS_PER_SEC * window):
            add("many_hosts", "info", len(hosts),
                f"tcp connections to {len(hosts)} different hosts on port {port} {within}, for example to "
                f"{min(hosts)}", port=port)

    findings.sort(key=lambda f: (RANK[f["kind"]], -f["count"], str(f.get("peer", "")), f.get("port") or 0))
    del findings[8:]
    sentences = [f["sentence"] for f in findings[:3]]
    if not sentences:
        # The busiest peer is named so an explanation quotes an address that was really seen.
        est = [s for s in samples[-1].sockets if s.state == "ESTABLISHED"]
        loop = sum(_is_loopback(s.remote) for s in est)
        busiest, busy = Counter(s.remote for s in est).most_common(1)[0] if est else (None, 0)
        if not est:
            head = "no established connections"
        elif loop == len(est):
            head = f"{len(est)} established connections, all over loopback (busiest peer {busiest} with {busy})"
        else:
            head = (f"{len(est)} established connections to {_plural(len({s.remote for s in est}), 'host')}"
                    + (f" ({loop} of them loopback)" if loop else "") + f" (busiest peer {busiest} with {busy})")
        tail = _plural(new_total, "new connection") if new_total else "no new connections"
        if deltas:
            fails = deltas["AttemptFails"]
            tail += f", {_plural(fails, 'failed connection attempt')}" if fails else ", no failed attempts"
        sentences = [f"{head}, {tail} {within}"]

    top = sorted(peers.items(), key=lambda kv: (-kv[1]["new"], -len(kv[1]["ports"]), kv[0]))[:5]
    return {
        "window_seconds": round(window, 2),
        "samples": len(samples),
        "socket_table": {
            "observed": len(seen),
            "new": new_total,
            "established_last_sample": sum(1 for s in samples[-1].sockets if s.state == "ESTABLISHED"),
            "peers": [{"peer": peer, "direction": "in" if inbound else "out", "target_ports": len(p["ports"]),
                       "new_target_ports": len(p["new_ports"]), "new": p["new"],
                       "observed": sum(p["outcomes"].values()), "states": dict(p["outcomes"])}
                      for (inbound, peer), p in top],
        },
        "counters": deltas,
        "counters_note": note,
        "findings": findings,
        "description": "; ".join(sentences),
    }


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), None
    except OSError as e:
        return None, f"{path}: {e.strerror or e}"


def snapshot(t=0.0, proc=PROC):
    """One read of the real files -> (Sample, notes)."""
    tcp, err = _read(proc.tcp)
    if tcp is None:
        raise MonitorError(f"cannot read {err}. The live monitor needs Linux with a readable /proc/net.")
    tcp6, err6 = _read(proc.tcp6)
    snmp, errs = _read(proc.snmp)
    notes = ([f"{err6} (IPv6 sockets not sampled)"] if err6 else []) + (
        [f"{errs} (kernel counters omitted)"] if errs else [])
    return Sample(t, parse_socktab(tcp) + parse_socktab(tcp6 or ""), parse_snmp(snmp or "") or None), notes


def sample_window(seconds, interval=INTERVAL, proc=PROC):
    """Samples from now for `seconds` -> (samples, notes). Ctrl-C keeps the samples taken so far."""
    count = max(2, math.ceil(seconds / interval - 1e-9) + 1)
    samples, notes, start = [], [], time.monotonic()
    try:
        for k in range(count):
            if k:
                time.sleep(max(0.0, start + k * interval - time.monotonic()))
            smp, errs = snapshot(time.monotonic() - start, proc)
            samples.append(smp)
            notes.extend(e for e in errs if e not in notes)
    except KeyboardInterrupt:
        if len(samples) < 2:
            raise
        notes.append("interrupted: the window is shorter than requested")
    return samples, notes


def detector_verdict(description):
    """The row bin/explain writes for one flow item, without the LLM -> (row, None) or (None, reason)."""
    try:
        from . import cli, detect, llm
    except ImportError as e:
        return None, f"detector unavailable ({e}); point HC_PY at the project venv or install requirements.txt"
    lab, score, ev = detect.classify_any("flow", description)
    row = {"id": "live", "verdict": cli.VERDICT[lab], "score": round(score, 4),
           "category": llm.scam_type("flow", description, lab), "actions": llm.actions_for("flow", lab, description),
           "evidence_used": ev}
    return row, None


def explained_row(description):
    """The same row with the Llama explanation: exactly what bin/explain produces for one flow item."""
    from . import cli
    with tempfile.TemporaryDirectory(prefix="prahari-monitor-") as tmp:
        src, dst = Path(tmp) / "in.jsonl", Path(tmp) / "out.jsonl"
        cli.write_jsonl(src, [dict(id="live", kind="flow", input=description)])
        cli.cmd_explain(argparse.Namespace(inp=src, out=dst))
        return cli.read_jsonl(dst)[0]


def run(args):
    """One window -> (findings JSON with a "verdict" row, exit code)."""
    samples, notes = sample_window(args.seconds, args.interval)
    result = summarise(samples)
    result["sources"] = [f"socket table {PROC.tcp}, {PROC.tcp6}: {len(samples)} samples, {args.interval:g} s apart",
                         f"kernel counters {PROC.snmp}: first and last sample"]
    result["notes"] = notes
    code = 0
    if args.explain:
        try:
            result["verdict"] = explained_row(result["description"])
            return result, 0
        except Exception as e:  # the window is still worth showing; fall back to the plain verdict
            notes.append(f"explanation unavailable: {type(e).__name__}: {e}")
            code = 2
    row, why = detector_verdict(result["description"])
    if row:
        result["verdict"] = row
    else:
        result["verdict_error"], code = why, 3
    return result, code


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="monitor",
        description="Sample this device's TCP socket table and kernel counters for one window, print the "
                    "findings and classify the description with the flow rules. Linux only; no root and no "
                    "packet capture. Exit status 0: sampled and classified; 2: could not sample or explain; "
                    "3: sampled, but the detector's dependencies are missing.")
    ap.add_argument("--seconds", type=float, default=10.0, help="window length in seconds (default 10)")
    ap.add_argument("--interval", type=float, default=INTERVAL, help="seconds between samples (default 0.5)")
    ap.add_argument("--explain", action="store_true",
                    help="also run the Llama explainer on the description, as bin/explain does for one item")
    a = ap.parse_args(argv)
    if not a.interval <= a.seconds <= 3600 or not 0.05 <= a.interval <= 5:
        ap.error("--seconds must be between one --interval and 3600, and --interval between 0.05 and 5")
    try:
        result, code = run(a)
    except MonitorError as e:
        print(f"monitor: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
