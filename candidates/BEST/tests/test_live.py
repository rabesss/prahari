"""Live monitor: parsing, window summaries, and descriptions the existing flow rules understand."""
import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAND))
from triage import live, llm, rules  # noqa: E402

HEADER4 = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"
HEADER6 = ("  sl  local_address                         remote_address                        st tx_queue "
           "rx_queue tr tm->when retrnsmt   uid  timeout inode")
TAIL = " 00000000:00000000 00:00000000 00000000  1000        0 12345 1 00000000938243cb 100 0 0 10 0"
TCP = "\n".join([HEADER4,
                 "   0: 0100007F:0CEA 00000000:0000 0A" + TAIL,            # 127.0.0.1:3306 listening
                 "   1: 8200A8C0:E862 517CA112:01BB 01" + TAIL,          # 192.168.0.130:59490 -> 18.161.124.81:443
                 "   2: 8200A8C0:C350 0A00000A:0016 02" + TAIL,          # -> 10.0.0.10:22, still connecting
                 "   3: 0100007F:C350 0100007F:B797 06" + TAIL,          # loopback, closed and in time-wait
                 "   4: 00000000:0016 00000000:0000 0a" + TAIL])         # lowercase hex, sshd listening
TCP6 = "\n".join([HEADER6,
                  "   0: 00000000000000000000000001000000:1538 00000000000000000000000000000000:0000 0A" + TAIL,
                  "   1: 5C117AFD0000E0A100000000488D01C7:9C81 00000000000000000000000000000000:0000 0A" + TAIL,
                  "   2: 0000000000000000FFFF00000100007F:0CEA 0000000000000000FFFF00008200A8C0:C350 01" + TAIL])
SNMP = "\n".join([
    "Ip: Forwarding DefaultTTL InReceives InHdrErrors",
    "Ip: 2 64 0 0",
    "Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs "
    "OutSegs RetransSegs InErrs OutRsts InCsumErrors",
    "Tcp: 1 200 120000 -1 151491 17991 63635 2314 101 11387241 12038791 9909 33 113899 0",
    "Udp: InDatagrams NoPorts InErrors OutDatagrams",
    "Udp: 15000 12 0 15001",
])
S = live.Socket
ME, PEER = "192.168.0.130", "93.184.216.34"
BASE = (S("0.0.0.0", 22, "0.0.0.0", 0, "LISTEN"), S(ME, 40000, PEER, 443), S(ME, 40001, "1.1.1.1", 443),
        S("127.0.0.1", 3306, "127.0.0.1", 0, "LISTEN"), S("127.0.0.1", 51000, "127.0.0.1", 3306))


def hex4(ip):
    return socket.inet_aton(ip)[::-1].hex().upper()


def hex6(ip):
    raw = ipaddress.IPv6Address(ip).packed
    return "".join(raw[i:i + 4][::-1].hex().upper() for i in range(0, 16, 4))


def line(local, lport, remote, rport, state):
    a, b = (hex6 if ":" in ip else hex4 for ip in (local, remote))
    return f"   0: {a}:{lport:04X} {b}:{rport:04X} {state:02X}" + TAIL


def snmp(**delta):
    base = dict(ActiveOpens=151491, PassiveOpens=17991, AttemptFails=63635, EstabResets=2314, OutRsts=113899,
                InErrs=33, RetransSegs=9909)
    return {k: v + delta.get(k, 0) for k, v in base.items()}


def window(rows, first=None, last=None, step=0.5):
    """One Sample per row; counters sit on the first and the last sample, as the sampler delivers them."""
    return [live.Sample(i * step, rows[i], first if i == 0 else last if i == len(rows) - 1 else None)
            for i in range(len(rows))]


def names(description):
    return sorted({n for n, _ in rules.flow_text_indicators(description)})


def kinds(summary):
    return [f["kind"] for f in summary["findings"]]


# ---- parsing -------------------------------------------------------------------------------------

def test_kernel_hex_is_little_endian_per_32_bit_word():
    assert hex4("127.0.0.1") == "0100007F" and hex4(ME) == "8200A8C0"
    assert hex6("fd7a:115c:a1e0::c701:8d48") == "5C117AFD0000E0A100000000488D01C7"
    assert hex6("::ffff:192.168.0.130") == "0000000000000000FFFF00008200A8C0"  # as the tcp6 fixture spells it


def test_parse_socktab_ipv4():
    socks = live.parse_socktab(TCP)
    assert [(s.local, s.local_port, s.remote, s.remote_port, s.state) for s in socks] == [
        ("127.0.0.1", 3306, "0.0.0.0", 0, "LISTEN"),
        (ME, 59490, "18.161.124.81", 443, "ESTABLISHED"),
        (ME, 50000, "10.0.0.10", 22, "SYN_SENT"),
        ("127.0.0.1", 50000, "127.0.0.1", 46999, "TIME_WAIT"),
        ("0.0.0.0", 22, "0.0.0.0", 0, "LISTEN")]


def test_parse_socktab_ipv6_and_v4_mapped():
    socks = live.parse_socktab(TCP6)
    assert (socks[0].local, socks[0].local_port, socks[0].state) == ("::1", 5432, "LISTEN")
    assert socks[1].local == "fd7a:115c:a1e0::c701:8d48" and socks[1].local_port == 40065
    # A dual-stack socket in tcp6 carries an IPv4 peer as ::ffff:a.b.c.d; it is reported as IPv4.
    assert (socks[2].local, socks[2].local_port, socks[2].remote, socks[2].remote_port) == (
        "127.0.0.1", 3306, ME, 50000)


def test_parse_socktab_skips_malformed_lines():
    broken = "\n".join([HEADER4, "", "garbage without colons", "   0: ZZ:GG 0100007F:0001 01",
                        "   1: 0100007F 00000000:0000 0A", "   2: 0100007F:0001 00000000:0000",
                        "   3: 0100007F:0001 00000000:0000 FF" + TAIL, "   4: 0100007F:0002 0100007F:0003 0C" + TAIL])
    socks = live.parse_socktab(broken)
    assert [(s.local_port, s.remote_port, s.state) for s in socks] == [(1, 0, "OTHER"), (2, 3, "SYN_RECV")]


def test_parse_snmp_reads_the_tcp_block():
    assert live.parse_snmp(SNMP) == dict(RtoAlgorithm=1, RtoMin=200, RtoMax=120000, MaxConn=-1, ActiveOpens=151491,
                                         PassiveOpens=17991, AttemptFails=63635, EstabResets=2314, CurrEstab=101,
                                         InSegs=11387241, OutSegs=12038791, RetransSegs=9909, InErrs=33,
                                         OutRsts=113899, InCsumErrors=0)
    assert live.parse_snmp(SNMP, proto="Udp")["NoPorts"] == 12
    assert live.parse_snmp("") == {} and live.parse_snmp("Tcp: ActiveOpens\n") == {}


def test_counter_deltas():
    deltas, note = live.counter_deltas(snmp(), snmp(AttemptFails=150, OutRsts=2))
    assert deltas["AttemptFails"] == 150 and deltas["OutRsts"] == 2 and deltas["PassiveOpens"] == 0 and not note
    deltas, note = live.counter_deltas(snmp(), snmp(AttemptFails=-1))
    assert deltas is None and "backwards" in note
    deltas, note = live.counter_deltas({"ActiveOpens": 1}, {"ActiveOpens": 2})
    assert deltas is None and "missing" in note
    assert live.counter_deltas(None, None)[0] is None


# ---- what a window shows ------------------------------------------------------------------------

def test_quiet_window_reports_what_is_open():
    s = live.summarise(window([BASE] * 21, snmp(), snmp(ActiveOpens=4, AttemptFails=3)))
    assert kinds(s) == [] and s["description"] == (
        "3 established connections to 3 hosts (1 of them loopback) (busiest peer 93.184.216.34 with 1), "
        "no new connections, 3 failed connection attempts within 10 seconds")
    assert names(s["description"]) == []
    assert s["counters"] == dict(ActiveOpens=4, PassiveOpens=0, AttemptFails=3, EstabResets=0, OutRsts=0, InErrs=0,
                                 RetransSegs=0)
    assert (s["socket_table"]["observed"], s["socket_table"]["new"], s["samples"]) == (3, 0, 21)


@pytest.mark.parametrize("count", [0, 1, 9, 10, 99, 150])
def test_quiet_wording_never_trips_a_rule(count):
    """Counts alone (new connects, background failures) must not read as an attack."""
    rows = [list(BASE)] + [list(BASE) + [S(ME, 41000 + i, PEER, 443, "TIME_WAIT") for i in range(count)]] * 4
    s = live.summarise(window(rows, snmp(), snmp(ActiveOpens=count + 23, AttemptFails=23)))
    assert kinds(s) == [] and names(s["description"]) == [] and "refus" not in s["description"]
    new = "no new connections" if not count else f"{count} new connection" + ("" if count == 1 else "s")
    assert f"{new}, 23 failed connection attempts" in s["description"]


def test_port_scan_on_loopback_is_counted_once():
    scan = [S("127.0.0.1", 30000 + i, "127.0.0.1", 47000 + i) for i in range(150)]
    listens = [S("127.0.0.1", 47000 + i, "127.0.0.1", 0, "LISTEN") for i in range(150)]
    served = [S("127.0.0.1", 47000 + i, "127.0.0.1", 30000 + i) for i in range(150)]  # the server end
    left = [S("127.0.0.1", 30000 + i, "127.0.0.1", 47000 + i, "TIME_WAIT") for i in range(150)]
    s = live.summarise(window([list(BASE) + listens] + [list(BASE) + listens + scan + served] * 3
                              + [list(BASE) + listens + left] * 17,
                              snmp(), snmp(ActiveOpens=153)))
    finding, = s["findings"]
    assert finding["kind"] == "port_scan" and finding["direction"] == "out"
    assert (finding["count"], finding["opened_in_window"], finding["peer"]) == (150, 150, "127.0.0.1")
    assert s["description"] == ("tcp connections to 150 different ports on 127.0.0.1 within 10 seconds, "
                                "all established when sampled")
    assert names(s["description"]) == ["port_scan"] and not rules.BENIGN_FLOW.search(s["description"])


def test_port_scan_in_time_wait_and_to_an_unanswering_host():
    closed = [S(ME, 43000 + i, "10.0.0.5", 30000 + i, "TIME_WAIT") for i in range(40)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + closed] * 20, snmp(), snmp()))
    assert s["description"] == ("tcp connections to 40 different ports on 10.0.0.5 within 10 seconds, all already "
                                "closed (in time-wait)")
    waiting = [S(ME, 44000 + i, "10.0.0.6", 31000 + i, "SYN_SENT") for i in range(25)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + waiting] * 20, snmp(), snmp(AttemptFails=3)))
    assert s["description"] == ("tcp connections to 25 different ports on 10.0.0.6 within 10 seconds, all still "
                                "waiting for a reply")
    assert names(s["description"]) == ["port_scan"]


def test_scan_left_over_from_before_the_window_says_so():
    left = [S(ME, 45000 + i, "10.0.0.5", 30000 + i, "TIME_WAIT") for i in range(45)]
    s = live.summarise(window([list(BASE) + left] * 21, snmp(), snmp()))
    assert kinds(s) == ["port_scan"] and s["socket_table"]["new"] == 0
    assert s["description"] == ("tcp connections to 45 different ports on 10.0.0.5 during 10 seconds of sampling, "
                                "all already closed (in time-wait), some opened before the window")


def test_incoming_scan_is_seen_on_listening_ports():
    listens = [S("0.0.0.0", 47100 + i, "0.0.0.0", 0, "LISTEN") for i in range(20)]
    accepted = [S(ME, 47100 + i, "10.0.0.5", 40000 + i) for i in range(20)]
    s = live.summarise(window([list(BASE) + listens] + [list(BASE) + listens + accepted] * 20, snmp(), snmp()))
    assert kinds(s) == ["port_scan"] and s["findings"][0]["direction"] == "in"
    assert s["description"] == ("incoming tcp connections from 10.0.0.5 to 20 different ports on this device within "
                                "10 seconds, all established when sampled")


def test_small_scan_stays_a_number_not_a_finding():
    few = [S("127.0.0.1", 30000 + i, "127.0.0.1", 47000 + i) for i in range(11)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + few] * 20, snmp(), snmp(ActiveOpens=11)))
    assert kinds(s) == [] and s["socket_table"]["peers"][0]["new_target_ports"] == 11
    assert names(s["description"]) == []


def test_login_port_repeats_read_as_password_guessing():
    rows = [list(BASE)]
    for i in range(20):  # four fresh sessions a second from one address, each gone by the next sample
        rows.append(list(BASE) + [S(ME, 22, "198.51.100.7", 51000 + 4 * i + j) for j in range(4)])
    s = live.summarise(window(rows, snmp(), snmp(ActiveOpens=80)))
    assert kinds(s) == ["login_port_repeats"] and names(s["description"]) == ["brute_force"]
    assert s["description"] == ("80 new connections to ssh port 22 on 192.168.0.130 from 198.51.100.7 within 10 "
                                "seconds, consistent with repeated ssh login attempts")
    assert llm.scam_type("flow", s["description"], 1) == "a brute-force login"
    assert "not whether a login succeeded" in s["findings"][0]["note"]


def test_login_port_made_by_this_device_and_a_quiet_ssh_port():
    made = [S(ME, 46000 + i, "203.0.113.9", 3389, "SYN_SENT") for i in range(30)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + made] * 20, snmp(), snmp()))
    assert s["description"] == ("30 new connections from this device to rdp port 3389 on 203.0.113.9 within 10 "
                                "seconds, consistent with repeated rdp login attempts")
    assert names(s["description"]) == ["brute_force"]
    seven = [S(ME, 47000 + i, "203.0.113.9", 22) for i in range(7)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + seven] * 20, snmp(), snmp()))
    assert kinds(s) == [] and names(s["description"]) == []


def test_half_open_connections_read_as_a_flood():
    flood = [S(ME, 443, "203.0.113.5", 52000 + i, "SYN_RECV") for i in range(80)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + flood] * 20, snmp(), snmp()))
    assert kinds(s) == ["half_open"] and names(s["description"]) == ["flood"]
    assert s["description"] == "80 half-open connections waiting on port 443 within 10 seconds"
    assert s["findings"][0]["peers"] == ["203.0.113.5"]


def test_regularly_spaced_connections_read_as_periodic():
    rows = [list(BASE) + [S(ME, 41000 + j, "203.0.113.9", 443, "TIME_WAIT") for j in range(i // 4)]
            for i in range(21)]
    s = live.summarise(window(rows, snmp(), snmp(ActiveOpens=5)))
    assert kinds(s) == ["periodic"] and names(s["description"]) == ["periodic"]
    assert s["description"] == ("5 new connections to 203.0.113.9 port 443 within 10 seconds at regular intervals "
                                "of about 2.0 seconds")
    burst = [list(BASE) + [S(ME, 41000 + j, "203.0.113.9", 443, "TIME_WAIT") for j in range(min(5, i))] for i in range(21)]
    assert kinds(live.summarise(window(burst, snmp(), snmp()))) == []  # all at once: not a beacon
    local = [list(BASE) + [S("127.0.0.1", 41000 + j, "127.0.0.1", 8080, "TIME_WAIT") for j in range(i // 4)]
             for i in range(21)]
    assert kinds(live.summarise(window(local, snmp(), snmp()))) == []  # loopback polling is ordinary


def test_failed_connect_burst_is_rejected_without_a_target():
    s = live.summarise(window([list(BASE)] * 13, snmp(), snmp(ActiveOpens=160, AttemptFails=150, OutRsts=151)))
    assert kinds(s) == ["failed_connects"] and s["counters"]["AttemptFails"] == 150
    # 151 resets in 6 seconds is this desktop's background rate, so they are not called out
    assert s["description"] == ("kernel counters: 150 connection attempts failed (refused or timed out) within 6 "
                                "seconds; sampling caught too few of them to name a target address or port")
    assert names(s["description"]) == ["rejected"]


def test_background_failures_are_not_called_rejected():
    s = live.summarise(window([list(BASE)] * 21, snmp(), snmp(ActiveOpens=45, AttemptFails=23, OutRsts=37)))
    assert kinds(s) == [] and names(s["description"]) == []
    assert "23 failed connection attempts within 10 seconds" in s["description"]
    s = live.summarise(window([list(BASE)] * 21, snmp(), snmp(OutRsts=400)))
    assert kinds(s) == ["resets_sent"] and names(s["description"]) == ["rejected"]
    assert s["description"] == "kernel counters: 400 reset packets were sent by this device within 10 seconds"


def test_many_hosts_on_one_port_is_reported_without_a_rule():
    many = [S(ME, 42000 + i, f"198.18.0.{i // 250}.{i % 250 + 1}", 445, "SYN_SENT") for i in range(60)]
    s = live.summarise(window([list(BASE)] + [list(BASE) + many] * 20, snmp(), snmp()))
    assert kinds(s) == ["many_hosts"] and s["findings"][0]["severity"] == "info"
    assert names(s["description"]) == [] and "60 different hosts on port 445" in s["description"]


def test_untrusted_or_missing_counters_are_said_so():
    s = live.summarise(window([list(BASE)] * 5, snmp(), snmp(AttemptFails=-5)))
    assert s["counters"] is None and "backwards" in s["counters_note"]
    assert names(s["description"]) == [] and "failed" not in s["description"]
    s = live.summarise(window([list(BASE)] * 3, None, None))
    assert s["counters"] is None and "unavailable" in s["counters_note"] and "failed" not in s["description"]


def test_findings_are_ranked_and_the_description_fits_the_prompt():
    scan = [S(ME, 46000 + i, "10.0.0.5", 30000 + i) for i in range(40)]
    flood = [S(ME, 443, "203.0.113.5", 52000 + i, "SYN_RECV") for i in range(60)]
    rows = [list(BASE)] + [list(BASE) + scan + flood + [S(ME, 22, "198.51.100.7", 51000 + i) for i in range(10)]] * 20
    s = live.summarise(window(rows, snmp(), snmp(AttemptFails=500, OutRsts=500)))
    assert kinds(s) == ["login_port_repeats", "half_open", "port_scan", "failed_connects"]
    # The three most important sentences go into the description, within the explainer's 320-character snippet.
    assert len(s["description"]) <= 320 and names(s["description"]) == ["brute_force", "flood", "port_scan"]
    with pytest.raises(ValueError):
        live.summarise(window([list(BASE)]))


def test_explainer_evidence_quotes_what_was_seen():
    quiet = live.summarise(window([list(BASE)] * 3, snmp(), snmp()))["description"]
    assert llm.compact_evidence("flow", quiet, [], 0) == ["traffic involving 93.184.216.34"]
    scan = "tcp connections to 150 different ports on 127.0.0.1 within 10 seconds, all established when sampled"
    assert llm.compact_evidence("flow", scan, [], 1) == ["traffic to 150 different ports on 127.0.0.1",
                                                         "looks like a port scan"]


# ---- the existing detector -----------------------------------------------------------------------

def detect():
    pytest.importorskip("joblib")
    pytest.importorskip("numpy")
    try:
        from triage import detect as module
    except ImportError as e:
        pytest.skip(f"detector dependencies unavailable: {e}")
    return module


def scan_window():
    scan = [S("127.0.0.1", 30000 + i, "127.0.0.1", 47000 + i) for i in range(150)]
    return window([list(BASE)] + [list(BASE) + scan] * 20, snmp(), snmp(ActiveOpens=150))


def test_classify_any_calls_a_quiet_window_benign():
    s = live.summarise(window([list(BASE)] * 21, snmp(), snmp(ActiveOpens=4, AttemptFails=3)))
    label, score, evidence = detect().classify_any("flow", s["description"])
    assert (label, score, evidence) == (0, 0.1, [])


def test_classify_any_verdicts_for_live_findings():
    d = detect()
    assert d.classify_any("flow", live.summarise(scan_window())["description"])[0] == 1
    rows = [list(BASE)] + [list(BASE) + [S(ME, 22, "198.51.100.7", 51000 + i) for i in range(4 * i)] for i in range(1, 21)]
    assert d.classify_any("flow", live.summarise(window(rows, snmp(), snmp()))["description"])[0] == 1
    refused = live.summarise(window([list(BASE)] * 21, snmp(), snmp(AttemptFails=150, OutRsts=151)))["description"]
    assert d.classify_any("flow", refused)[0] == "uncertain"  # a rejected burst without a target stays ambiguous


# ---- the real sampler and the entry points -------------------------------------------------------

linux = pytest.mark.skipif(not sys.platform.startswith("linux") or not os.access("/proc/net/tcp", os.R_OK),
                           reason="needs a readable /proc/net/tcp")


@linux
def test_sampler_reads_this_host():
    samples, notes = live.sample_window(0.6, 0.3)
    assert len(samples) == 3 and 0.55 <= samples[-1].t <= 1.5
    assert all(isinstance(s, live.Socket) and s.state in set(live.STATES.values()) | {"OTHER"}
               for smp in samples for s in smp.sockets)
    s = live.summarise(samples)
    assert s["samples"] == 3 and isinstance(s["description"], str) and s["description"]
    # What this host is doing is not controlled: only check the description is one the rules can read.
    assert set(names(s["description"])) <= {name for name, _, _ in rules.FLOW_RULES}


def test_sampler_reports_unreadable_files_instead_of_failing_loudly(tmp_path):
    (tmp_path / "tcp").write_text(TCP)
    (tmp_path / "tcp6").write_text("")
    (tmp_path / "snmp").write_text(SNMP)
    proc = live.Proc(str(tmp_path / "tcp"), str(tmp_path / "tcp6"), str(tmp_path / "snmp"))
    samples, notes = live.sample_window(0.2, 0.1, proc)
    assert len(samples) == 3 and not notes and samples[0].counters["AttemptFails"] == 63635
    with pytest.raises(live.MonitorError):
        live.sample_window(0.1, 0.1, live.Proc(str(tmp_path / "missing"), "", ""))
    (tmp_path / "snmp").unlink()
    (tmp_path / "tcp6").unlink()
    samples, notes = live.sample_window(0.1, 0.1, proc)
    assert samples[-1].counters is None and len(notes) == 2


@linux
def test_monitor_main_prints_one_json_document(capsys):
    code = live.main(["--seconds", "0.6", "--interval", "0.3"])
    out = json.loads(capsys.readouterr().out)
    assert code in (0, 3) and out["samples"] == 3 and out["description"]
    assert ("verdict" in out) != ("verdict_error" in out) and out["sources"]
    if "verdict" in out:
        assert set(out["verdict"]) == {"id", "verdict", "score", "category", "actions", "evidence_used"}


def test_monitor_help_works_without_the_detector():
    env = dict(os.environ, HC_PY=sys.executable)
    p = subprocess.run([str(CAND / "bin" / "monitor"), "--help"], env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "--seconds" in p.stdout and "--explain" in p.stdout and "packet capture" in p.stdout


DEMO = ["--ports", "3", "--repeat", "2", "--every", "0.02", "--delay", "0", "--base", "46300"]


def run_demo(*extra, host=None):
    demo = CAND / "bin" / "scan_demo.py"
    cmd = [sys.executable, str(demo)] + (["--host", host] if host else []) + DEMO + list(extra)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def test_scan_demo_refuses_anything_but_loopback():
    for host in ("203.0.113.5", "localhost", "::ffff:203.0.113.5"):
        p = run_demo(host=host)
        assert p.returncode == 2 and "loopback" in p.stderr and not p.stdout, host


@linux
def test_scan_demo_reports_closed_and_own_open_ports():
    """Loopback sockets only: ports nobody listens on, and the demo's own throwaway listeners."""
    closed = json.loads(run_demo().stdout)
    assert (closed["attempted"], closed["refused"], closed["connected"], closed["skipped_in_use"]) == (3, 3, 0, 0)
    assert closed["repeated"]["listener"] is False and closed["repeated"]["refused"] == 2
    opened = json.loads(run_demo("--open", "--hold", "0.1").stdout)
    assert (opened["attempted"], opened["connected"], opened["refused"]) == (3, 3, 0)
    assert opened["repeated"]["listener"] is True and opened["repeated"]["connected"] == 2


def test_missing_detector_dependencies_are_reported_not_raised(monkeypatch):
    import triage as package
    for name in ("cli", "detect"):  # as when joblib or scikit-learn is missing, whatever was imported before
        monkeypatch.setitem(sys.modules, f"triage.{name}", None)
        monkeypatch.delattr(package, name, raising=False)
    row, why = live.detector_verdict("tcp connections to 20 different ports on 10.0.0.5")
    assert row is None and why.startswith("detector unavailable") and "HC_PY" in why


@linux
def test_a_failing_explainer_still_leaves_the_findings_and_the_verdict(monkeypatch):
    def no_model(description):
        raise RuntimeError("no model")

    monkeypatch.setattr(live, "explained_row", no_model)
    result, code = live.run(argparse.Namespace(seconds=0.2, interval=0.1, explain=True))
    assert code in (2, 3) and result["notes"][-1] == "explanation unavailable: RuntimeError: no model"
    assert result["samples"] == 3 and ("verdict" in result) != ("verdict_error" in result)


def test_explain_reuses_the_bin_explain_code_path(monkeypatch):
    detect()  # cli imports the detector, so this needs its dependencies
    from triage import cli
    seen = {}

    def fake_explain(a):
        seen["rows"] = cli.read_jsonl(a.inp)
        cli.write_jsonl(a.out, [dict(id="live", verdict="benign", explanation="Checked.", explanation_status="success")])

    monkeypatch.setattr(cli, "cmd_explain", fake_explain)
    row = live.explained_row("a live description")
    assert row["explanation"] == "Checked." and seen["rows"] == [dict(id="live", kind="flow", input="a live description")]
