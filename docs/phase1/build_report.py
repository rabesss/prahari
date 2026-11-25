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
from matplotlib import patheffects
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
# Galaxy S23 bars: one teal family (intermediate build a lighter shade); Neoverse bars stay indigo.
TEAL = "#0F766E"
TEAL_LIGHT = "#5EB8AE"

# Every figure is drawn 6.5 in wide, the width it is placed at in the PDF, so font sizes
# below are the printed sizes. Nothing is smaller than 10 pt.
FIG_W = 6.5
FT = 10.0    # tick labels, value labels, notes
FS = 10.5    # axis labels
FTITLE = 11.0
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


def _style_ax(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.set_facecolor(LIGHT_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SLATE_LIGHT)
    ax.spines["bottom"].set_color(SLATE_LIGHT)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(colors=SLATE, labelcolor=INK)


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
# Coloured by device: Neoverse in indigo shades, Galaxy S23 builds in teal (intermediate lighter).
ARM_TARGETS = [
    ("V2, 8 threads", 104.6, 0.98, INDIGO),
    ("V2, 2 threads", 46.7, 1.73, INDIGO),
    ("S23 first, warm", 43.4, 1.20, TEAL),
    ("S23 first, airplane", 39.0, 1.42, TEAL),
    ("S23 intermediate", 21.5, 2.90, TEAL_LIGHT),
    ("S23 final", 32.5, 1.86, TEAL),
    ("N1, 2 vCPU", 19.9, 3.84, INDIGO_MID),
]

# Galaxy S23 warm KYC check, total time per item (s), by build (Section 5).
S23_LATENCY = [
    ("First", 1.20, TEAL),
    ("First (airplane)", 1.42, TEAL),
    ("Intermediate", 2.90, TEAL_LIGHT),
    ("Final", 1.857, TEAL),
]

# Detection, conservative scoring (Table 8). FPR None = not recorded.
DETECTION = [
    # label, n, recall, fpr, f1, group
    ("SMS", "1,162", None, None, 0.925, "dev"),
    ("URL", "7,997", 0.988, 0.000, 0.994, "dev"),
    ("Indian\neval", "320", None, 0.031, 0.969, "dev"),
    ("NSL-KDD\nflow", "22.5k", 0.757, 0.030, 0.850, "dev"),
    ("v3", "81", 0.941, 0.000, 0.970, "held"),
    ("Blind\nvalidation", "240", 1.000, 0.107, 0.918, "held"),
    ("v4", "79", 0.969, 0.298, 0.805, "held"),
    ("Sealed", "184", 0.929, 0.300, 0.812, "held"),
]

# Galaxy S23 dumpsys meminfo App Summary (KiB), sum 1,744,842 KiB = 1,704 MiB total PSS.
MEM_ROWS = [
    ("Native heap", 1566056, INDIGO),
    ("Private other", 59764, INDIGO_MID),
    ("Graphics", 58676, SLATE),
    ("Code (.so, .apk)", 37420, SLATE),
    ("Java heap, system\nand stack", 11044 + 10566 + 1316, SLATE_LIGHT),
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
    c1x, c1w = 0.04, 1.62
    c2x, c2w = 1.96, 2.02
    c3x, c3w = 4.28, 2.18
    # Row centres: rows 1-2 feed Stage 2; row 3 (intrusion path) ends in an alert.
    r1, r2, r3 = 2.62, 1.68, 0.50
    h1, h2, h3 = 0.86, 0.70, 0.74

    hy = H - 0.12
    ax.text(c1x + c1w / 2, hy, "INPUT", ha="center", va="center", fontsize=FT, color=SLATE, weight="bold")
    ax.text(c2x + c2w / 2, hy, "DETECT (decides the verdict)", ha="center", va="center", fontsize=FT, color=INDIGO, weight="bold")
    ax.text(c3x + c3w / 2, hy, "EXPLAIN (on the device)", ha="center", va="center", fontsize=FT, color=SLATE_DARK, weight="bold")

    box(c1x, r1 - h1 / 2, c1w, h1, "SMS, link or UPI QR", "Android app or\nLinux CLI / UI", LIGHT_BG, BOX_EDGE)
    box(c1x, r2 - h2 / 2, c1w, h2, "Live socket monitor", "/proc/net/tcp, snmp", LIGHT_BG, BOX_EDGE)
    box(c1x, r3 - h3 / 2, c1w, h3, "NSL-KDD flow record", "bin/predict --task flow", LIGHT_BG, BOX_EDGE)

    box(c2x, r1 - h1 / 2, c2w, h1, "Stage 1: detectors", "Classifiers + Indian-context\nrules, 0.42 ms per item", INDIGO_LIGHT, INDIGO, INDIGO)
    box(c2x, r2 - h2 / 2, c2w, h2, "Flow text rules", "live network events", INDIGO_LIGHT, INDIGO, INDIGO)
    box(c2x, r3 - h3 / 2, c2w, h3, "Intrusion path", "HistGradientBoosting\n+ 3 intrusion rules", INDIGO_LIGHT, INDIGO, INDIGO)

    s2_top, s2_bot = r1 + h1 / 2, r2 - h2 / 2
    box(c3x, s2_bot, c3w, s2_top - s2_bot, "Stage 2: Llama 3.2 1B",
        "QLoRA INT4 on ExecuTorch\nXNNPACK, Arm CPU\nexplains typed evidence,\nhonesty and safety check;\nnever changes the verdict",
        SLATE_BG, SLATE_DARK, SLATE_DARK)
    box(c3x, r3 - h3 / 2, c3w, h3, "Alert with evidence", "verdict and evidence (no LLM)", LIGHT_BG, SLATE, INK)

    g = 0.03
    for r in (r1, r2, r3):
        arrow(c1x + c1w + g, c2x - g, r)
        arrow(c2x + c2w + g, c3x - g, r)

    # Thin divider between the message/network path and the intrusion path.
    ax.plot([0.04, W - 0.04], [1.08, 1.08], color=GRID, lw=1.0, ls="--", zorder=0)

    return _save(fig, "fig-architecture.png")


# ---------------------------------------------------------------------------
# Figure: Arm performance
# ---------------------------------------------------------------------------

def build_arm_perf_chart() -> Path:
    """(A) Neoverse-V2 thread scaling; (B) decode speed and item wall latency on every Arm target.

    The panels are separate subfigures so each gets its own width: B's long target names do
    not push A's plot area to the right. At 5.9 in tall it still fits on one page with its
    surrounding text; every label is at least 10 pt.
    """
    fig = plt.figure(figsize=(FIG_W, 5.9), dpi=DPI, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.06, hspace=0.03)
    sf_a, sf_b = fig.subfigures(2, 1, height_ratios=[1.0, 1.15])

    # Panel A
    ax1 = sf_a.subplots()
    _style_ax(ax1)
    x = np.arange(len(V2_THREADS))
    # Bars and latency markers share the tick positions, so each marker sits over its own bar.
    bars = ax1.bar(x, V2_DECODE, width=0.5, yerr=V2_DECODE_SD, capsize=3, color=INDIGO,
                   error_kw={"ecolor": INK, "lw": 0.9}, label="Decode speed (tok/s)", zorder=3)
    ax1.set_xticks(x, [f"{t} thread{'s' if t > 1 else ''}" for t in V2_THREADS])
    ax1.set_xlim(-0.5, 3.85)
    ax1.set_xlabel("ExecuTorch XNNPACK threads on Arm Neoverse-V2")
    ax1.set_ylabel("Decode speed (tok/s)", color=INDIGO)
    ax1.set_ylim(0, 165)
    ax1.set_yticks([0, 40, 80, 120])
    ax1.tick_params(axis="y", labelcolor=INDIGO)
    # Decode values sit just above each bar; the latency axis is scaled so every latency marker
    # and its error bar stays below the value label.
    for b, v in zip(bars, V2_DECODE):
        ax1.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.1f}", ha="center", va="bottom",
                 fontsize=FT, color=INDIGO, fontweight="bold")

    ax1b = ax1.twinx()
    ax1b.spines["top"].set_visible(False)
    ax1b.spines["left"].set_visible(False)
    ax1b.spines["right"].set_color(SLATE_LIGHT)
    halo = [patheffects.withStroke(linewidth=3.2, foreground="white")]
    ax1b.errorbar(x, V2_ITEM_WALL, yerr=V2_ITEM_SD, fmt="s--", color=SLATE_DARK, lw=1.6, ms=6, mec="white",
                  mew=1.0, capsize=3, label="Item time, wall latency (s)", zorder=4,
                  path_effects=halo)
    ax1b.set_ylim(0, 6.6)
    ax1b.set_ylabel("Item wall latency (s)", color=SLATE_DARK)
    ax1b.set_yticks([0, 1, 2, 3])
    ax1b.tick_params(axis="y", colors=SLATE, labelcolor=SLATE_DARK)
    # Labels sit above and to the right of each point: the line falls to the right, so that
    # corner is empty, and the offset clears the 4-thread error bar and its cap.
    for xi, v in zip(x, V2_ITEM_WALL):
        ax1b.text(xi + 0.29, v + 0.10, f"{v:.2f} s", ha="left", va="bottom", fontsize=FT, color=SLATE_DARK,
                  fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=GRID, lw=0.6, alpha=1.0),
                  zorder=5)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2, frameon=True, facecolor="white", edgecolor=GRID,
               borderaxespad=0.3)
    sf_a.suptitle("A. Neoverse-V2 thread scaling, Llama 3.2 1B INT4", x=0.01, ha="left",
                  fontsize=FTITLE, fontweight="bold", color=INK)

    # Panel B
    ax2 = sf_b.subplots()
    _style_ax(ax2, grid_axis="x")
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
    # The bars are descriptive: the note sits in the empty lower-right corner of the panel.
    ax2.text(156, -0.35, "Different builds and\nsessions; not a controlled\ncomparison. Gated pass:\nTable 6.",
             ha="right", va="bottom", fontsize=FT, color=SLATE_DARK, style="italic", linespacing=1.35,
             bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=GRID, lw=0.6), zorder=5)
    for b, v, l in zip(hb, tps, lat):
        cy = b.get_y() + b.get_height() / 2
        label = f"{v:.1f} tok/s · {l:.2f} s"
        ax2.text(v + 1.5, cy, label, ha="left", va="center", fontsize=FT, color=INK, fontweight="bold")
    families = [Patch(color=INDIGO, label="Neoverse-V2"), Patch(color=TEAL, label="Galaxy S23"),
                Patch(color=TEAL_LIGHT, label="S23 intermediate build"), Patch(color=INDIGO_MID, label="Neoverse-N1")]
    ax2.legend(handles=families, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False,
               handlelength=1.2, columnspacing=1.0, borderaxespad=0.2)
    sf_b.suptitle("B. Decode speed and item time (wall latency) on each Arm target", x=0.01, ha="left",
                  fontsize=FTITLE, fontweight="bold", color=INK)

    return _save(fig, "fig-arm-perf.png")


# ---------------------------------------------------------------------------
# Figure: detection (F1 vs FPR)
# ---------------------------------------------------------------------------

def build_eval_chart() -> Path:
    """Conservative F1 and FPR on every benchmark (Table 8).

    Value labels are horizontal. Within each group the two bars are spread apart (centres
    0.44 apart, width 0.30) so a label centred over one bar clears the neighbouring bar.
    An FPR that was not recorded is printed as an em dash; the caption explains it.
    """
    fig, ax = plt.subplots(figsize=(FIG_W, 3.0), dpi=DPI, layout="constrained")
    _style_ax(ax)
    labels = [f"{d[0]}\nn={d[1]}" for d in DETECTION]
    f1 = [d[4] for d in DETECTION]
    fpr = [d[3] for d in DETECTION]
    # Held-back groups are shifted right by GAP so the divider clears the labels beside it.
    GAP = 0.4
    x = np.array([i + (GAP if d[5] == "held" else 0.0) for i, d in enumerate(DETECTION)])
    off, w = 0.22, 0.30
    b1 = ax.bar(x - off, f1, width=w, color=INDIGO, label="Conservative F1", zorder=3)
    b2 = ax.bar(x + off, [v or 0 for v in fpr], width=w, color=AMBER, label="False positive rate (FPR)", zorder=3)
    ax.axvline(3.5 + GAP / 2, color=SLATE_LIGHT, ls="--", lw=0.9, zorder=2)
    ax.text(1.5, 1.115, "Development sets", ha="center", va="bottom", fontsize=FT, color=SLATE, style="italic")
    ax.text(5.5 + GAP, 1.115, "Held-back sets", ha="center", va="bottom", fontsize=FT, color=SLATE, style="italic")
    for b, v in zip(b1, f1):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.3f}", ha="center", va="bottom",
                fontsize=FT, color=INDIGO, fontweight="bold", zorder=4)
    for b, v in zip(b2, fpr):
        txt, base = ("n/r", 0.0) if v is None else (f"{v:.3f}", v)
        ax.text(b.get_x() + b.get_width() / 2, base + 0.015, txt, ha="center", va="bottom", fontsize=FT,
                color=AMBER_TEXT, fontweight="bold", zorder=4)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.6, x[-1] + 0.6)
    ax.set_ylim(0, 1.19)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Score or rate")
    fig.legend(*ax.get_legend_handles_labels(), loc="outside upper center", ncol=2, frameon=False)
    return _save(fig, "fig-eval-summary.png")


# ---------------------------------------------------------------------------
# Figure: Galaxy S23 memory
# ---------------------------------------------------------------------------

def build_memory_chart() -> Path:
    """Galaxy S23 dumpsys meminfo PSS breakdown after a KYC check."""
    fig, ax = plt.subplots(figsize=(FIG_W, 2.5), dpi=DPI, layout="constrained")
    _style_ax(ax, grid_axis="x")
    names = [r[0] for r in MEM_ROWS]
    mib = [r[1] / 1024 for r in MEM_ROWS]
    cols = [r[2] for r in MEM_ROWS]
    total_mib = MEM_TOTAL_KIB / 1024
    y = np.arange(len(names))[::-1]
    bars = ax.barh(y, mib, height=0.62, color=cols, zorder=3)
    ax.set_yticks(y, names)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 1800)
    ax.set_xlabel("Proportional set size, PSS (MiB)")
    for b, v in zip(bars, mib):
        cy = b.get_y() + b.get_height() / 2
        label = f"{v:,.0f} MiB ({100 * v / total_mib:.1f}%)"
        if v > 1000:
            ax.text(v - 20, cy, label, ha="right", va="center", fontsize=FT, color="white", fontweight="bold")
        else:
            ax.text(v + 20, cy, label, ha="left", va="center", fontsize=FT, color=INK, fontweight="bold")
    ax.text(0.985, 0.06,
            f"Total PSS {total_mib:,.0f} MiB (1.66 GiB)\nTotal RSS {MEM_RSS_MIB:,} MiB (1.78 GiB)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=FT, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", fc=INDIGO_LIGHT, ec=INDIGO, lw=0.8))
    return _save(fig, "fig-memory.png")


# ---------------------------------------------------------------------------
# Figure: results at a glance (2x2)
# ---------------------------------------------------------------------------

def build_overview_chart() -> Path:
    """One-page visual summary: detection, S23 latency, Neoverse-V2 throughput, S23 memory."""
    fig, axs = plt.subplots(2, 2, figsize=(FIG_W, 5.9), dpi=DPI, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.1, w_pad=0.1, hspace=0.08, wspace=0.06)
    (a, b), (c, d) = axs

    # (a) Detection on the held-back sets.
    _style_ax(a)
    held = [r for r in DETECTION if r[5] == "held"]
    x = np.arange(len(held))
    # Bars are narrower than their spacing so the FPR labels (wider than a bar) clear the
    # tall recall bar beside them; FPR labels also sit on white boxes above everything.
    w, off = 0.30, 0.20
    rb = a.bar(x - off, [r[2] for r in held], width=w, color=INDIGO, label="Recall", zorder=3)
    fb = a.bar(x + off, [r[3] for r in held], width=w, color=AMBER, label="FPR", zorder=3)
    # Every value label is horizontal and sits just above its bar.
    for bar, v in zip(rb, [r[2] for r in held]):
        a.text(bar.get_x() + bar.get_width() / 2, v + 0.02, f"{v:.2f}", ha="center", va="bottom",
               fontsize=FT, color=INDIGO, fontweight="bold")
    for bar, v in zip(fb, [r[3] for r in held]):
        a.text(bar.get_x() + bar.get_width() / 2, v + 0.03, f"{v:.2f}", ha="center", va="bottom",
               fontsize=FT, color=AMBER_TEXT, fontweight="bold", zorder=5,
               bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none"))
    # Short one-word set names keep each tick label to two lines at 10 pt.
    a.set_xticks(x, [f"{r[0].split(chr(10))[0]}\nn={r[1]}" for r in held])
    a.tick_params(axis="x", length=0)
    a.set_ylim(0, 1.32)
    a.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    a.legend(loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.02))
    a.set_ylabel("Recall or FPR")
    a.set_title("Detection on held-back sets", loc="left")

    # (b) Galaxy S23 warm KYC check latency. Horizontal bars so every build name fits on
    # one line without hyphenation.
    _style_ax(b, grid_axis="x")
    names = [s[0] for s in S23_LATENCY]
    vals = [s[1] for s in S23_LATENCY]
    yb = np.arange(len(vals))[::-1]
    b.axvspan(1.0, 2.0, color=INDIGO_LIGHT, ec="#C7D2FE", lw=0.8, zorder=1)
    bb = b.barh(yb, vals, height=0.6, color=[s[2] for s in S23_LATENCY], zorder=3)
    for bar, v in zip(bb, vals):
        b.text(v + 0.07, bar.get_y() + bar.get_height() / 2, f"{v:.2f} s", ha="left", va="center",
               fontsize=FT, color=INK, fontweight="bold")
    b.set_yticks(yb, names)
    b.tick_params(axis="y", length=0)
    b.set_ylim(-0.55, len(vals) - 0.45 + 0.75)
    b.set_xlim(0, 3.6)
    b.set_xticks([0, 1, 2, 3])
    b.set_xlabel("Total time per check (s)")
    b.text(1.5, len(vals) - 0.45 + 0.375, "1–2 s target", ha="center", va="center", fontsize=FT,
           color=INDIGO, fontweight="bold")
    b.set_title("Galaxy S23, warm KYC check", loc="left")

    # (c) Neoverse-V2 decode speed vs threads.
    _style_ax(c)
    c.errorbar(V2_THREADS, V2_DECODE, yerr=V2_DECODE_SD, fmt="o-", color=INDIGO, lw=2, ms=6, capsize=3, zorder=3)
    for t, v in zip(V2_THREADS, V2_DECODE):
        c.text(t, v + 7, f"{v:.1f}", ha="center", va="bottom", fontsize=FT, color=INDIGO, fontweight="bold")
    c.set_xscale("log", base=2)
    c.set_xticks(V2_THREADS, [str(t) for t in V2_THREADS])
    c.minorticks_off()
    c.set_xlim(0.8, 10)
    c.set_ylim(0, 130)
    c.set_xlabel("Threads")
    c.set_ylabel("Decode speed (tok/s)")
    c.set_title("Neoverse-V2 decode speed", loc="left")

    # (d) Galaxy S23 memory.
    _style_ax(d, grid_axis="x")
    total_mib = MEM_TOTAL_KIB / 1024
    native = MEM_ROWS[0][1] / 1024
    rows = [("Total RSS", MEM_RSS_MIB, SLATE_LIGHT), ("Total PSS", total_mib, SLATE),
            ("Native heap", native, INDIGO), ("Everything\nelse", total_mib - native, INDIGO_MID)]
    yd = np.arange(len(rows))[::-1]
    db = d.barh(yd, [r[1] for r in rows], height=0.6, color=[r[2] for r in rows], zorder=3)
    for bar, r in zip(db, rows):
        cy = bar.get_y() + bar.get_height() / 2
        d.text(r[1] + 40, cy, f"{r[1]:,.0f}", ha="left", va="center", fontsize=FT, color=INK, fontweight="bold")
    d.set_yticks(yd, [r[0] for r in rows])
    d.tick_params(axis="y", length=0)
    d.set_xlim(0, 2450)
    d.set_xticks([0, 500, 1000, 1500, 2000])
    d.set_xlabel("MiB after a KYC check")
    d.set_title("Galaxy S23 memory", loc="left")

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
        "geometry:top=0.85in,bottom=0.85in,left=0.85in,right=0.85in,headsep=14pt,footskip=26pt",
        "-V",
        "classoption=table",
        "-V",
        "fontsize=10pt",
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
