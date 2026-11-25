#!/usr/bin/env python3
"""Reproducibly generate report charts and build docs/phase1/report.pdf.

Run from anywhere in the repository:
    python3 docs/phase1/build_report.py                # charts + PDF
    python3 docs/phase1/build_report.py --charts-only  # charts only

Outputs (each figure as vector PDF, used by the report, and as PNG for Markdown viewers):
    docs/phase1/img/fig-architecture.{pdf,png}
    docs/phase1/img/fig-overview.{pdf,png}
    docs/phase1/img/fig-arm-perf.{pdf,png}
    docs/phase1/img/fig-eval-summary.{pdf,png}
    docs/phase1/img/fig-memory.{pdf,png}
    docs/phase1/report.pdf

All plotted numbers come directly from verified project artifacts documented in
docs/phase1/EVIDENCE.md (Samsung Galaxy S23 RTL run 8, Arm Neoverse-V2 benchmark,
Oracle Arm Neoverse-N1 eval, PR #42 v3 dev holdout, and sealed holdout records).
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
import numpy as np

PHASE1 = Path(__file__).resolve().parent
REPO = PHASE1.parents[1]
IMG_DIR = PHASE1 / "img"
REPORT_MD = PHASE1 / "report.md"
REPORT_PDF = PHASE1 / "report.pdf"
HEADER_TEX = PHASE1 / "pdf-header.tex"
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB form limit

# Palette: indigo for measured values and the detector path, slate for context and
# comparison bars. Amber (orange) is reserved for false positive rate (FPR) and is used
# nowhere else in any figure.
INDIGO = "#3730A3"
INDIGO_DARK = "#1E1B4B"
INDIGO_LIGHT = "#EEF2FF"
INDIGO_MID = "#6366F1"
AMBER = "#B45309"       # FPR only
AMBER_TEXT = "#92400E"  # FPR value labels only
SLATE = "#475569"
SLATE_DARK = "#334155"
SLATE_BG = "#F1F5F9"
SLATE_LIGHT = "#94A3B8"
INK = "#0F172A"
LIGHT_BG = "#F8FAFC"
GRID = "#E2E8F0"
BOX_EDGE = "#CBD5E1"
# Galaxy S23 bars: one teal family (intermediate build a lighter shade). Neoverse-V2 bars are
# indigo and Neoverse-N1 bars slate grey, so the two server cores never share a hue.
TEAL = "#0F766E"
TEAL_LIGHT = "#5EB8AE"
N1_SLATE = "#64748B"

# Every figure is drawn 6.36 in wide, the text width it is placed at in the PDF, so font
# sizes below are the printed sizes. Nothing is smaller than 10 pt.
FIG_W = 6.36
FT = 10.5    # tick labels, value labels, notes
FS = 11.0    # axis labels
FTITLE = 11.5
FT1 = 12.5   # Figure 1 (results at a glance) labels, set larger than the rest
FT5 = 11.0   # Figure 5 (detection summary) labels
DPI = 220

plt.rcParams.update({
    "font.family": ["IBM Plex Sans", "DejaVu Sans"],
    "font.size": FT,
    "axes.titlesize": FTITLE,
    "axes.labelsize": FS,
    "xtick.labelsize": FT,
    "ytick.labelsize": FT,
    "legend.fontsize": FT,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.labelcolor": SLATE,
    "pdf.fonttype": 42,  # embed TrueType so figure text stays selectable and crisp
})


def _style_ax(ax: plt.Axes, grid_axis: str | None = None) -> None:
    """Common axes style. Charts with value labels pass no grid axis: a gridline drawn behind a
    label crosses its text, and the labels already carry the values."""
    ax.set_facecolor(LIGHT_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SLATE_LIGHT)
    ax.spines["bottom"].set_color(SLATE_LIGHT)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SLATE, labelcolor=INK)


def _keep_clear(fig: plt.Figure, texts, bars, pad_pt: float = 3.0) -> None:
    """Nudge each value label sideways until it clears every bar it is not attached to.

    texts and bars are parallel lists: texts[i] belongs to bars[i]. A label that overlaps any
    other bar (by its rendered extent plus pad_pt) moves away from that bar's centre.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    pad = pad_pt * fig.dpi / 72
    for t, own in zip(texts, bars):
        ax = t.axes
        for _ in range(40):
            tb = t.get_window_extent(r)
            hit = None
            for b in bars:
                if b is own:
                    continue
                bb = b.get_window_extent(r)
                if (tb.x0 < bb.x1 + pad and tb.x1 > bb.x0 - pad and tb.y0 < bb.y1 + pad and tb.y1 > bb.y0 - pad):
                    hit = bb
                    break
            if hit is None:
                break
            step = 1.0 if (tb.x0 + tb.x1) / 2 >= (hit.x0 + hit.x1) / 2 else -1.0
            x, y = t.get_position()
            px = ax.transData.transform((x, y))
            t.set_position(ax.transData.inverted().transform((px[0] + step * 1.5, px[1])))


def _save(fig: plt.Figure, name: str) -> Path:
    """Write the figure as vector PDF (placed in the report) and as PNG; return the PDF path."""
    out = IMG_DIR / name
    fig.savefig(out, dpi=DPI, facecolor="white")
    pdf = out.with_suffix(".pdf")
    fig.savefig(pdf, facecolor="white", metadata={"CreationDate": None})
    plt.close(fig)
    return pdf


# ---------------------------------------------------------------------------
# Data. Every number below also appears in docs/phase1/report.md.
# ---------------------------------------------------------------------------

# Neoverse-V2 ExecuTorch XNNPACK thread scaling: 3 runs x 6 items, mean +/- SD (Table 7).
V2_THREADS = np.array([1, 2, 4, 8])
V2_DECODE = np.array([25.69, 46.69, 75.89, 104.58])
V2_DECODE_SD = np.array([0.16, 0.12, 0.43, 1.15])
V2_ITEM_WALL = np.array([2.792, 1.728, 1.470, 0.980])
V2_ITEM_SD = np.array([0.031, 0.002, 0.377, 0.015])

# Llama 3.2 1B INT4 decode speed and per-item wall latency on each Arm target, top to bottom.
# Coloured by device: Neoverse-V2 indigo, Neoverse-N1 slate grey, Galaxy S23 builds teal
# (intermediate lighter).
# The printed item time keeps the precision of its source (Tables 1, 6 and 7, Sections 5.1-5.2), so
# each value reads the same here as in the text.
ARM_TARGETS = [
    ("V2, 8 threads", 104.6, "0.980", INDIGO),
    ("V2, 2 threads", 46.7, "1.728", INDIGO),
    ("S23 first, warm", 43.4, "1.20", TEAL),
    ("S23 first, airplane", 39.0, "1.42", TEAL),
    ("S23 intermediate", 21.5, "2.90", TEAL_LIGHT),
    ("S23 final (all-items)", 32.5, "1.857", TEAL),
    ("N1, 2 vCPU", 19.9, "3.84", N1_SLATE),
]

# Galaxy S23 warm KYC check, total time per item (s), by build (Section 5, Table 6): label,
# seconds, printed value, colour, hatch. The final build has two passes: Llama on all items
# (1.857 s) and the later, hotter flagged-only gated pass (2.611 s), shown hatched.
S23_LATENCY = [
    ("First", 1.20, "1.20 s", TEAL, None),
    ("First, airplane", 1.42, "1.42 s", TEAL, None),
    ("Intermediate", 2.90, "2.90 s", TEAL_LIGHT, None),
    ("Final, all items", 1.857, "1.857 s", TEAL, None),
    ("Final, gated", 2.611, "2.611 s", TEAL, "///"),
]

# Detection, conservative scoring (Table 8). FPR None = not recorded.
DETECTION = [
    # label, n, recall, fpr, f1, group
    ("SMS", "1,162", None, None, 0.925, "dev"),
    ("URL", "7,997", 0.988, 0.000, 0.994, "dev"),
    ("Indian eval", "320", None, 0.031, 0.969, "dev"),
    ("NSL-KDD", "22,544", 0.757, 0.030, 0.850, "dev"),
    ("v3", "81", 0.941, 0.000, 0.970, "held"),
    ("Blind set", "240", 1.000, 0.107, 0.918, "held"),
    ("v4", "79", 0.969, 0.298, 0.805, "held"),
    ("Sealed", "184", 0.929, 0.300, 0.812, "held"),
]

# Galaxy S23 dumpsys meminfo App Summary (KiB), sum 1,744,842 KiB = 1,704 MiB total PSS.
# One colour per category: the native heap indigo, the four small categories distinct shades.
MEM_ROWS = [
    ("Native heap", 1566056, INDIGO),
    ("Private other", 59764, TEAL),
    ("Graphics", 58676, INDIGO_MID),
    ("Code (.so, .apk)", 37420, SLATE_LIGHT),
    ("Java heap, system, stack", 11044 + 10566 + 1316, SLATE_DARK),
]
MEM_TOTAL_KIB = 1744842
MEM_RSS_MIB = 1824


# ---------------------------------------------------------------------------
# Figure: architecture
# ---------------------------------------------------------------------------

def build_architecture_chart() -> Path:
    """Two-stage pipeline: inputs -> detectors (decide) -> on-device explanation or alert."""
    W, H = FIG_W, 3.55
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    def box(x, y, w, h, title, sub, fc, ec, tc=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc=fc, ec=ec, lw=1.2))
        n_sub = sub.count("\n") + 1 if sub else 0
        line = 0.175  # in, for 10 pt text with spacing
        block = 0.21 + n_sub * line
        top = y + h / 2 + block / 2
        ax.text(x + w / 2, top - 0.105, title, ha="center", va="center", fontsize=FS, weight="bold", color=tc)
        if sub:
            ax.text(x + w / 2, top - 0.21 - n_sub * line / 2, sub, ha="center", va="center",
                    fontsize=FT, color=SLATE, linespacing=1.25)

    def arrow(x0, x1, y0, y1=None):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y0 if y1 is None else y1), arrowstyle="-|>",
                                     mutation_scale=11, lw=1.3, color=SLATE, shrinkA=0, shrinkB=0))

    # Columns (inches).
    # The gap between DETECT and EXPLAIN is wide enough to label the live monitor's arrow.
    c1x, c1w = 0.03, 1.56
    c2x, c2w = 1.83, 1.90
    c3x, c3w = 4.63, 1.70
    # Row centres: rows 1-2 feed Stage 2; row 3 (intrusion path) ends in an alert.
    r1, r2, r3 = 2.62, 1.68, 0.50
    h1, h2, h3 = 0.86, 0.70, 0.74

    hy = H - 0.12
    # All three column headers share one slate colour; indigo is reserved for the DETECT boxes.
    ax.text(c1x + c1w / 2, hy, "INPUT", ha="center", va="center", fontsize=FT, color=SLATE_DARK, weight="bold")
    ax.text(c2x + c2w / 2, hy, "DETECT (decides the verdict)", ha="center", va="center", fontsize=FT, color=SLATE_DARK, weight="bold")
    ax.text(c3x + c3w / 2, hy, "EXPLAIN (on the device)", ha="center", va="center", fontsize=FT, color=SLATE_DARK, weight="bold")

    box(c1x, r1 - h1 / 2, c1w, h1, "SMS, link or UPI QR", "Android app or\nLinux CLI / UI", LIGHT_BG, BOX_EDGE)
    box(c1x, r2 - h2 / 2, c1w, h2, "Live socket monitor", "/proc/net/tcp, snmp", LIGHT_BG, BOX_EDGE)
    box(c1x, r3 - h3 / 2, c1w, h3, "NSL-KDD flow record", "bin/predict --task flow", LIGHT_BG, BOX_EDGE)

    box(c2x, r1 - h1 / 2, c2w, h1, "Stage 1: detectors", "Classifiers + Indian-context\nrules; 0.42 ms/item\non Neoverse-N1", INDIGO_LIGHT, INDIGO, INDIGO)
    box(c2x, r2 - h2 / 2, c2w, h2, "Flow text rules", "live network events", INDIGO_LIGHT, INDIGO, INDIGO)
    box(c2x, r3 - h3 / 2, c2w, h3, "Intrusion path", "HistGradientBoosting\n+ 3 intrusion rules", INDIGO_LIGHT, INDIGO, INDIGO)

    s2_top, s2_bot = r1 + h1 / 2, r2 - h2 / 2
    box(c3x, s2_bot, c3w, s2_top - s2_bot, "Stage 2: Llama 3.2 1B",
        "QLoRA INT4 on\nExecuTorch\nXNNPACK, Arm CPU;\nexplains typed\nevidence, honesty\nand safety check;\nnever changes\nthe verdict",
        SLATE_BG, SLATE_DARK, SLATE_DARK)
    box(c3x, r3 - h3 / 2, c3w, h3, "Alert with evidence", "verdict and evidence\n(no LLM)", LIGHT_BG, SLATE, INK)

    g = 0.03
    for r in (r1, r2, r3):
        arrow(c1x + c1w + g, c2x - g, r)
        arrow(c2x + c2w + g, c3x - g, r)
    # The live monitor can add an optional Llama explanation (Section 3.4); label that arrow.
    ax.text((c2x + c2w + c3x) / 2, r2 + 0.06, "optional\nexplanation", ha="center", va="bottom", fontsize=10,
            color=SLATE, style="italic", linespacing=1.1)

    # Thin divider between the message/network path and the intrusion path.
    ax.plot([0.04, W - 0.04], [1.08, 1.08], color=GRID, lw=1.0, ls="--", zorder=0)

    return _save(fig, "fig-architecture.png")


# ---------------------------------------------------------------------------
# Figure: Arm performance
# ---------------------------------------------------------------------------

def build_arm_perf_chart() -> Path:
    """(A) Neoverse-V2 thread scaling; (B) decode speed and item wall latency on every Arm target.

    The panels are separate subfigures so each gets its own width: B's long target names do
    not push A's plot area to the right. At 4.5 in tall it still fits on one page with its
    surrounding text; every label is at least 10 pt.
    """
    fig = plt.figure(figsize=(FIG_W, 4.5), dpi=DPI, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.06, hspace=0.03)
    sf_a, sf_b = fig.subfigures(2, 1, height_ratios=[1.0, 1.15])

    # Panel A: two side-by-side plots sharing the thread axis. Decode speed is drawn as bars and
    # item wall latency as its own line plot, so the latency series never sits on the bars.
    ax1, ax1b = sf_a.subplots(1, 2, width_ratios=[1.1, 1.0])
    x = np.arange(len(V2_THREADS))
    thread_ticks = [str(t) for t in V2_THREADS]

    _style_ax(ax1)
    bars = ax1.bar(x, V2_DECODE, width=0.56, yerr=V2_DECODE_SD, capsize=3, color=INDIGO,
                   error_kw={"ecolor": INK, "lw": 0.9}, zorder=3)
    ax1.set_xticks(x, thread_ticks)
    ax1.tick_params(axis="x", length=0)
    ax1.set_xlabel("Threads")
    ax1.set_ylabel("Decode speed (tok/s)")
    ax1.set_ylim(0, 125)
    ax1.set_yticks([0, 40, 80, 120])
    for b_, v, sd in zip(bars, V2_DECODE, V2_DECODE_SD):
        ax1.text(b_.get_x() + b_.get_width() / 2, v + sd + 3, f"{v:.1f}", ha="center", va="bottom",
                 fontsize=FT, color=INDIGO, fontweight="bold")

    _style_ax(ax1b)
    ax1b.errorbar(x, V2_ITEM_WALL, yerr=V2_ITEM_SD, fmt="s-", color=SLATE_DARK, lw=1.6, ms=6, mec="white",
                  mew=1.0, capsize=3, zorder=4)
    ax1b.set_xticks(x, thread_ticks)
    ax1b.tick_params(axis="x", length=0)
    ax1b.set_xlim(-0.5, 3.5)
    ax1b.set_xlabel("Threads")
    ax1b.set_ylabel("Item wall latency (s)")
    ax1b.set_ylim(0, 3.6)
    ax1b.set_yticks([0, 1, 2, 3])
    # Every label is centred above its own marker, clear of the top of its error bar; the 2-thread
    # label sits higher so the steep segment from the 1-thread point does not cross it, and the
    # 8-thread label sits higher so the falling segment from the 4-thread point stays below it.
    for xi, v, sd in zip(x, V2_ITEM_WALL, V2_ITEM_SD):
        ax1b.text(xi, v + sd + (0.42 if xi in (1, 3) else 0.14), f"{v:.3f} s", ha="center", va="bottom", fontsize=FT, color=SLATE_DARK,
                  fontweight="bold", zorder=5)
    sf_a.suptitle("A. Neoverse-V2 thread scaling, Llama 3.2 1B INT4 (ExecuTorch XNNPACK)", x=0.01,
                  ha="left", fontsize=FTITLE, fontweight="bold", color=INK)

    # Panel B
    ax2 = sf_b.subplots()
    _style_ax(ax2)
    names = [t[0] for t in ARM_TARGETS]
    tps = [t[1] for t in ARM_TARGETS]
    lat = [t[2] for t in ARM_TARGETS]
    cols = [t[3] for t in ARM_TARGETS]
    y = np.arange(len(names))[::-1]
    hb = ax2.barh(y, tps, height=0.66, color=cols, zorder=3)
    ax2.set_yticks(y, names)
    ax2.tick_params(axis="y", length=0)
    ax2.set_xlim(0, 158)
    ax2.set_ylim(-0.55, len(names) - 0.45)
    ax2.set_xlabel("Decode speed (tok/s)")
    # No in-plot note: the figure caption states that the bars are not a controlled comparison.
    for b, v, l in zip(hb, tps, lat):
        cy = b.get_y() + b.get_height() / 2
        label = f"{v:.1f} tok/s · {l} s"
        ax2.text(v + 1.5, cy, label, ha="left", va="center", fontsize=FT, color=INK, fontweight="bold")
    families = [Patch(color=INDIGO, label="Neoverse-V2"), Patch(color=N1_SLATE, label="Neoverse-N1"),
                Patch(color=TEAL, label="Galaxy S23"), Patch(color=TEAL_LIGHT, label="S23 intermediate")]
    ax2.legend(handles=families, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False,
               handlelength=1.1, handletextpad=0.5, columnspacing=0.9, borderaxespad=0.2)
    sf_b.suptitle("B. Decode speed and item time (wall latency) on each Arm target", x=0.01, ha="left",
                  fontsize=FTITLE, fontweight="bold", color=INK)

    return _save(fig, "fig-arm-perf.png")


# ---------------------------------------------------------------------------
# Figure: detection (F1 vs FPR)
# ---------------------------------------------------------------------------

def _overlaps(fig: plt.Figure, texts, bars, pad_pt: float = 2.0) -> list[str]:
    """Return the labels whose rendered extent touches a bar other than their own."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    pad = pad_pt * fig.dpi / 72
    bad = []
    for t, own in zip(texts, bars):
        tb = t.get_window_extent(r)
        for bar in bars:
            if bar is own:
                continue
            bb = bar.get_window_extent(r)
            if tb.x0 < bb.x1 + pad and tb.x1 > bb.x0 - pad and tb.y0 < bb.y1 + pad and tb.y1 > bb.y0 - pad:
                bad.append(t.get_text())
                break
    return bad


def build_eval_chart() -> Path:
    """Conservative F1 and FPR on every benchmark (Table 8).

    Every value label is horizontal and centred a fixed 0.035 above its own bar; none is nudged.
    The bars of a group are spread apart (centres 0.50 apart, width 0.20) so a label wider than
    its bar still clears the neighbouring bar; the build fails if any label touches another bar.
    An FPR that was not recorded is printed as an em dash, as in Table 8; the caption explains it.
    Type is set at FT5 (11 pt), larger than the other charts, since the figure is read closely.
    """
    with plt.rc_context({"font.size": FT5, "xtick.labelsize": 10.0, "ytick.labelsize": FT5,
                         "axes.labelsize": FT5, "legend.fontsize": FT5}):
        return _build_eval_chart()


def _build_eval_chart() -> Path:
    fig, ax = plt.subplots(figsize=(FIG_W, 3.25), dpi=DPI, layout="constrained")
    _style_ax(ax)
    labels = [f"{d[0]}\nn = {d[1]}" for d in DETECTION]
    f1 = [d[4] for d in DETECTION]
    fpr = [d[3] for d in DETECTION]
    # Bar-group centres: the development groups sit wider apart, since their tick labels
    # ("Indian eval", "n = 22,544") are longer; the held-back groups follow a gap (divider).
    x = np.array([0.0, 1.18, 2.35, 3.58, 4.78, 5.78, 6.78, 7.78])
    off, w = 0.25, 0.20
    b1 = ax.bar(x - off, f1, width=w, color=INDIGO, label="Conservative F1", zorder=3)
    b2 = ax.bar(x + off, [v or 0 for v in fpr], width=w, color=AMBER, label="False positive rate (FPR)", zorder=3)
    ax.axvline((x[3] + x[4]) / 2, color=SLATE_LIGHT, ls="--", lw=0.9, zorder=2)
    # Group labels sit above the plot frame, each over a bracket spanning its group's bars.
    tr = ax.get_xaxis_transform()  # x in data units, y in axes fraction
    for lo, hi, name in ((0, 3, "Development sets"), (4, 7, "Held-back sets")):
        x0, x1 = x[lo] - off - w / 2, x[hi] + off + w / 2
        ax.plot([x0, x0, x1, x1], [1.03, 1.06, 1.06, 1.03], transform=tr, color=SLATE_LIGHT, lw=0.9,
                clip_on=False)
        ax.text((x0 + x1) / 2, 1.08, name, transform=tr, ha="center", va="bottom", fontsize=FT5,
                color=SLATE, style="italic")
    texts, owners = [], []
    PAD = 0.035
    for bar, v in zip(b1, f1):
        # A background patch keeps the group divider from crossing the v3 label.
        texts.append(ax.text(bar.get_x() + bar.get_width() / 2, v + PAD, f"{v:.3f}", ha="center", va="bottom",
                             fontsize=FT5, color=INDIGO, fontweight="bold", zorder=4,
                             bbox=dict(fc=LIGHT_BG, ec="none", pad=0.6)))
        owners.append(bar)
    for bar, v in zip(b2, fpr):
        txt, base = ("—", 0.0) if v is None else (f"{v:.3f}", v)
        texts.append(ax.text(bar.get_x() + bar.get_width() / 2, base + PAD, txt, ha="center", va="bottom",
                             fontsize=FT5, color=AMBER_TEXT, fontweight="bold", zorder=4))
        owners.append(bar)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", length=0, pad=5)
    # Extra room on the left so the first value label (0.925) clears the y axis.
    ax.set_xlim(x[0] - 0.68, x[-1] + 0.54)
    ax.set_ylim(0, 1.22)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_ylabel("Score or rate")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside upper center", ncol=2, frameon=False)
    bad = _overlaps(fig, texts, owners)
    if bad:
        raise RuntimeError(f"Figure 5 value labels touch another bar: {bad}")
    # Neighbouring tick labels ("NSL-KDD / n = 22,544") must not touch each other.
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ext = [t.get_window_extent(r) for t in ax.get_xticklabels()]
    for e0, e1 in zip(ext, ext[1:]):
        if e0.x1 + 12 > e1.x0:
            raise RuntimeError(f"Figure 5 tick labels touch each other: {[(round(a.x0), round(a.x1)) for a in ext]}")
    return _save(fig, "fig-eval-summary.png")


# ---------------------------------------------------------------------------
# Figure: Galaxy S23 memory
# ---------------------------------------------------------------------------

def build_memory_chart() -> Path:
    """Galaxy S23 dumpsys meminfo PSS breakdown after a KYC check, as one stacked strip.

    The strip is 1.25 in tall: the native heap carries its value inside the bar, and the four small
    categories are named in a legend; Section 5.4 states every category's value in the text.
    """
    fig, ax = plt.subplots(figsize=(FIG_W, 1.25), dpi=DPI, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.02)
    _style_ax(ax)
    ax.spines["left"].set_visible(False)
    total_mib = MEM_TOTAL_KIB / 1024
    left = 0.0
    handles = []
    for (name, kib, col) in MEM_ROWS:
        v = kib / 1024
        ax.barh(0, v, left=left, height=0.62, color=col, edgecolor="white", linewidth=0.8, zorder=3)
        if v > 1000:
            ax.text(left + v / 2, 0, f"Native heap {v:,.0f} MiB ({100 * v / total_mib:.1f}%)", ha="center",
                    va="center", fontsize=FT, color="white", fontweight="bold", zorder=4)
        else:
            handles.append(Patch(color=col, label=name.replace("\n", " ")))
        left += v
    ax.set_yticks([])
    ax.set_ylim(-0.45, 0.45)
    ax.set_xlim(0, total_mib)
    ax.set_xticks([0, 500, 1000, 1500])
    ax.tick_params(axis="x", pad=2)
    ax.set_xlabel("PSS (MiB)", labelpad=1)
    ax.set_title("Galaxy S23 memory by category", loc="left", fontsize=FT, pad=4)
    ax.set_title(f"Total PSS {total_mib:,.0f} MiB · total RSS {MEM_RSS_MIB:,} MiB", loc="right",
                 fontsize=FT, fontweight="normal", color=INDIGO, pad=4)
    fig.legend(handles=handles, loc="outside lower center", ncol=4, frameon=False, fontsize=FT,
               handlelength=1.0, handletextpad=0.4, columnspacing=1.0)
    return _save(fig, "fig-memory.png")


# ---------------------------------------------------------------------------
# Figure: results at a glance (three panels)
# ---------------------------------------------------------------------------

def _inside(fig: plt.Figure, ax: plt.Axes, texts, pad_pt: float = 1.0) -> list[str]:
    """Return the labels whose rendered extent leaves the axes' plot area."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    box = ax.get_window_extent(r)
    pad = pad_pt * fig.dpi / 72
    return [t.get_text() for t in texts
            if (lambda b: b.x0 < box.x0 + pad or b.x1 > box.x1 - pad or b.y1 > box.y1 - pad)(t.get_window_extent(r))]


def build_overview_chart() -> Path:
    """One-figure summary: held-back detection, S23 warm latency by build, Neoverse-V2 decode speed.

    Figure 1 sits on the first pages, so its type is set larger than the other figures (11.5 pt
    labels), close to the 10.5 pt body text as printed. Memory has its own figure (Figure 4), so it is
    not repeated here.
    """
    with plt.rc_context({"font.size": FT1, "xtick.labelsize": FT1, "ytick.labelsize": FT1,
                         "axes.labelsize": FT1, "legend.fontsize": FT1, "axes.titlesize": 13.0}):
        return _build_overview_chart()


def _build_overview_chart() -> Path:
    fig = plt.figure(figsize=(FIG_W, 4.45), dpi=DPI, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.08, w_pad=0.08, hspace=0.07, wspace=0.05)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], width_ratios=[1.15, 1.0])
    a = fig.add_subplot(gs[0, :])
    b = fig.add_subplot(gs[1, 0])
    c = fig.add_subplot(gs[1, 1])

    # (a) Detection on the held-back sets, across the full width so every label (three decimals,
    # as in Table 8) has room: within a group the recall and FPR labels clear the other bar.
    _style_ax(a)
    held = [r for r in DETECTION if r[5] == "held"]
    names = {"v3": "India v3 split", "Blind set": "Blind set", "v4": "India v4 split", "Sealed": "Sealed holdout"}
    x = np.arange(len(held))
    w, off = 0.28, 0.20
    rb = a.bar(x - off, [r[2] for r in held], width=w, color=INDIGO, label="Recall", zorder=3)
    fb = a.bar(x + off, [r[3] for r in held], width=w, color=AMBER, label="FPR", zorder=3)
    a_texts, a_owners = [], []
    for bar, v in zip(rb, [r[2] for r in held]):
        a_texts.append(a.text(bar.get_x() + bar.get_width() / 2, v + 0.025, f"{v:.3f}", ha="center",
                              va="bottom", fontsize=FT1, color=INDIGO, fontweight="bold"))
        a_owners.append(bar)
    for bar, v in zip(fb, [r[3] for r in held]):
        a_texts.append(a.text(bar.get_x() + bar.get_width() / 2, v + 0.025, f"{v:.3f}", ha="center",
                              va="bottom", fontsize=FT1, color=AMBER_TEXT, fontweight="bold", zorder=5))
        a_owners.append(bar)
    a.set_xticks(x, [f"{names[r[0]]}\nn = {r[1]}" for r in held])
    a.tick_params(axis="x", length=0)
    a.set_xlim(-0.62, len(held) - 0.38)
    a.set_ylim(0, 1.2)
    a.set_yticks([0, 0.5, 1.0])
    a.set_ylabel("Recall or FPR")
    a.set_title("Detection on held-back sets", loc="left")
    a.legend(loc="lower right", bbox_to_anchor=(1.0, 0.98), ncol=2, frameon=False, borderaxespad=0.0,
             handlelength=1.1, columnspacing=1.0)

    # (b) Galaxy S23 warm KYC check latency. Horizontal bars so every build name fits on one line.
    _style_ax(b)
    bnames = [s[0] for s in S23_LATENCY]
    vals = [s[1] for s in S23_LATENCY]
    yb = np.arange(len(vals))[::-1]
    # The target band is a fill only (no edge lines), drawn beneath everything else.
    b.axvspan(1.0, 2.0, fc=INDIGO_LIGHT, ec="none", lw=0, zorder=0)
    bb = b.barh(yb, vals, height=0.62, color=[s[3] for s in S23_LATENCY], zorder=3)
    b_texts = []
    for bar, s in zip(bb, S23_LATENCY):
        if s[4]:
            bar.set_hatch(s[4])
            bar.set_edgecolor("white")
            bar.set_linewidth(0)
        b_texts.append(b.text(s[1] + 0.07, bar.get_y() + bar.get_height() / 2, s[2], ha="left", va="center",
                              fontsize=FT1, color=INK, fontweight="bold"))
    b.set_yticks(yb, bnames)
    b.tick_params(axis="y", length=0)
    b.set_ylim(-0.55, len(vals) - 0.45 + 1.0)
    b.set_xlim(0, 4.3)
    b.set_xticks([0, 1, 2, 3, 4])
    b.set_xlabel("Total time per check (s)")
    b_texts.append(b.text(1.5, len(vals) - 0.45 + 0.5, "1–2 s target", ha="center", va="center", fontsize=FT1,
                          color=INDIGO, fontweight="bold"))
    b.set_title("S23 warm KYC check", loc="left")

    # (c) Neoverse-V2 decode speed vs threads.
    _style_ax(c)
    c.errorbar(V2_THREADS, V2_DECODE, yerr=V2_DECODE_SD, fmt="o-", color=INDIGO, lw=2, ms=6, capsize=3, zorder=3)
    c_texts = []
    for t, v in zip(V2_THREADS, V2_DECODE):
        c_texts.append(c.text(t, v + 7, f"{v:.1f}", ha="center", va="bottom", fontsize=FT1, color=INDIGO,
                              fontweight="bold"))
    c.set_xscale("log", base=2)
    c.set_xticks(V2_THREADS, [str(t) for t in V2_THREADS])
    c.minorticks_off()
    c.set_xlim(0.7, 11.5)
    c.set_ylim(0, 132)
    c.set_xlabel("Threads")
    c.set_ylabel("Decode speed (tok/s)")
    c.set_title("Neoverse-V2 decode", loc="left")

    _keep_clear(fig, a_texts, a_owners)
    bad = _overlaps(fig, a_texts, a_owners) + _inside(fig, a, a_texts) + _inside(fig, b, b_texts) \
        + _inside(fig, c, c_texts)
    if bad:
        raise RuntimeError(f"Figure 1 labels touch another bar or leave their panel: {bad}")
    return _save(fig, "fig-overview.png")


def build_pdf() -> None:
    if not shutil.which("pandoc") or not shutil.which("xelatex"):
        raise RuntimeError("Both pandoc and xelatex must be on PATH to build report.pdf")

    cmd = [
        "pandoc",
        str(REPORT_MD),
        "-o",
        str(REPORT_PDF),
        "--from=markdown+pipe_tables+grid_tables+fenced_code_blocks+backtick_code_blocks+yaml_metadata_block+link_attributes",
        "--pdf-engine=xelatex",
        f"--include-in-header={HEADER_TEX}",
        f"--resource-path={PHASE1}:{REPO}",
        "--shift-heading-level-by=-1",
        "--number-sections",
        "-V",
        "geometry:top=0.75in,bottom=0.75in,left=1.07in,right=1.07in,headsep=14pt,footskip=26pt",
        "-V",
        "classoption=table",
        "-V",
        "fontsize=11pt",
        "-V",
        "papersize=letter",
    ]
    res = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
        raise RuntimeError(f"pandoc failed with exit code {res.returncode}")
    if res.stderr.strip():
        print("pandoc warnings:\n" + res.stderr.strip())


def verify_pdf() -> None:
    if not REPORT_PDF.is_file():
        raise RuntimeError(f"Expected PDF not found: {REPORT_PDF}")
    size = REPORT_PDF.stat().st_size
    if size == 0 or size > MAX_PDF_BYTES:
        raise RuntimeError(f"PDF size {size} bytes is outside (0, {MAX_PDF_BYTES}]")
    sha = hashlib.sha256(REPORT_PDF.read_bytes()).hexdigest()
    pages = "unknown"
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(REPORT_PDF)], text=True, capture_output=True, check=True).stdout
        for line in info.splitlines():
            if line.startswith("Pages:"):
                pages = line.split(":", 1)[1].strip()
                break
    print(f"Built {REPORT_PDF.relative_to(REPO)}: {size:,} bytes ({size / (1024 * 1024):.2f} MiB), {pages} pages")
    print(f"SHA-256: {sha}")


def main() -> int:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    charts = [
        build_architecture_chart(),
        build_overview_chart(),
        build_arm_perf_chart(),
        build_eval_chart(),
        build_memory_chart(),
    ]
    print("Generated charts: " + ", ".join(str(c.relative_to(REPO)) for c in charts))
    if "--charts-only" in sys.argv[1:]:
        return 0
    build_pdf()
    verify_pdf()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
