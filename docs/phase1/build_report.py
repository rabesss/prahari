#!/usr/bin/env python3
"""Reproducibly generate report charts and build docs/phase1/report.pdf.

Run from anywhere in the repository:
    python3 docs/phase1/build_report.py

Outputs:
    docs/phase1/img/fig-arm-perf.png
    docs/phase1/img/fig-eval-summary.png
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
import numpy as np

PHASE1 = Path(__file__).resolve().parent
REPO = PHASE1.parents[1]
IMG_DIR = PHASE1 / "img"
REPORT_MD = PHASE1 / "report.md"
REPORT_PDF = PHASE1 / "report.pdf"
HEADER_TEX = PHASE1 / "pdf-header.tex"
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB form limit

INDIGO = "#1E3A8A"
BLUE = "#2563EB"
TEAL = "#0F766E"
AMBER = "#D97706"
RED = "#DC2626"
SLATE = "#475569"
LIGHT_BG = "#F8FAFC"
GRID = "#E2E8F0"


def _style_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(LIGHT_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#94A3B8")
    ax.spines["bottom"].set_color("#94A3B8")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def build_arm_perf_chart() -> Path:
    """Two-panel Arm performance & KleidiAI utilization figure."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.1), dpi=220)
    fig.patch.set_facecolor("white")

    # Panel A: Arm Neoverse-V2 thread scaling (3 repeats x 6 items, mean +/- SD)
    threads = np.array([1, 2, 4, 8])
    decode_tps = np.array([25.69, 46.69, 75.89, 104.58])
    decode_sd = np.array([0.16, 0.12, 0.43, 1.15])
    item_wall = np.array([2.792, 1.728, 1.470, 0.980])
    item_sd = np.array([0.031, 0.002, 0.377, 0.015])

    _style_ax(ax1)
    x = np.arange(len(threads))
    bars = ax1.bar(
        x - 0.17,
        decode_tps,
        width=0.34,
        yerr=decode_sd,
        capsize=3,
        color=INDIGO,
        label="Decode speed (tok/s)",
        zorder=3,
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{t}T" for t in threads], fontsize=9.5)
    ax1.set_xlabel("ExecuTorch XNNPACK threadpool (Arm Neoverse-V2)", fontsize=9.5, color=SLATE)
    ax1.set_ylabel("Decode throughput (tok/s)", fontsize=9.5, color=INDIGO)
    ax1.set_ylim(0, 125)
    ax1.tick_params(axis="y", labelcolor=INDIGO, labelsize=9)
    for b, v in zip(bars, decode_tps):
        ax1.text(b.get_x() + b.get_width() / 2, v + 3.0, f"{v:.1f}", ha="center", va="bottom", fontsize=8, color=INDIGO, fontweight="bold")

    ax1b = ax1.twinx()
    ax1b.spines["top"].set_visible(False)
    ax1b.spines["right"].set_color(TEAL)
    ax1b.spines["left"].set_visible(False)
    ax1b.errorbar(
        x + 0.17,
        item_wall,
        yerr=item_sd,
        fmt="o-",
        color=TEAL,
        linewidth=2.0,
        markersize=5.5,
        capsize=3,
        label="Item wall latency (s)",
        zorder=4,
    )
    ax1b.set_ylabel("Item wall latency (s)", fontsize=9.5, color=TEAL)
    ax1b.set_ylim(0, 3.6)
    ax1b.tick_params(axis="y", labelcolor=TEAL, labelsize=9)
    for idx, (xi, v) in enumerate(zip(x + 0.17, item_wall)):
        if idx == 2:
            ax1b.text(xi + 0.08, v + 0.04, f"{v:.2f}s", ha="left", va="bottom", fontsize=8, color=TEAL, fontweight="bold")
        else:
            offset = 0.18 if idx < 2 else 0.16
            ax1b.text(xi, v + offset, f"{v:.2f}s", ha="center", va="bottom", fontsize=8, color=TEAL, fontweight="bold")
    ax1.set_title("A. Neoverse-V2 Thread Scaling (Llama 3.2 1B INT4)", fontsize=10.2, fontweight="bold", color="#0F172A", pad=10)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center", frameon=True, facecolor="white", edgecolor=GRID, fontsize=8)

    # Panel B: Cross-target Arm comparison + KleidiAI CPU share callout
    _style_ax(ax2)
    targets = [
        "Oracle N1\n(2 vCPU)",
        "Galaxy S23\n(Airplane)",
        "Galaxy S23\n(Warm)",
        "Neoverse-V2\n(2T)",
        "Neoverse-V2\n(8T)",
    ]
    tps_vals = [19.9, 39.0, 43.4, 46.7, 104.6]
    lat_vals = [3.84, 1.42, 1.20, 1.73, 0.98]
    colors = [SLATE, TEAL, BLUE, INDIGO, "#312E81"]
    y = np.arange(len(targets))

    ax2.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax2.grid(axis="y", visible=False)
    hbars = ax2.barh(y, tps_vals, height=0.56, color=colors, zorder=3)
    ax2.set_yticks(y)
    ax2.set_yticklabels(targets, fontsize=8.8)
    ax2.set_xlabel("Llama 3.2 1B INT4 decode speed (tok/s)", fontsize=9.5, color=SLATE)
    ax2.set_xlim(0, 165)
    ax2.set_ylim(-0.65, 4.55)
    ax2.tick_params(axis="x", labelsize=9)
    for b, tps, lat in zip(hbars, tps_vals, lat_vals):
        ax2.text(
            tps + 2.2,
            b.get_y() + b.get_height() / 2,
            f"{tps:.1f} tok/s ({lat:.2f} s)",
            va="center",
            ha="left",
            fontsize=8.0,
            color="#0F172A",
            fontweight="bold",
        )
    ax2.set_title("B. Measured Arm Hardware Targets", fontsize=10.2, fontweight="bold", color="#0F172A", pad=10)
    ax2.text(
        0.98,
        0.04,
        "Neoverse-V2 perf (2T, 2,222 samples):\n54.17% CPU in KleidiAI kai_* kernels\n23.27% i8mm prefill · 20.57% dotprod",
        transform=ax2.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.2,
        color="#1E293B",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#EFF6FF", edgecolor="#93C5FD", linewidth=0.8),
    )

    fig.tight_layout(pad=1.4)
    out = IMG_DIR / "fig-arm-perf.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def build_eval_and_mem_chart() -> Path:
    """Two-panel honest evaluation & Galaxy S23 memory breakdown figure."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.1), dpi=220)
    fig.patch.set_facecolor("white")

    # Panel A: F1 & FPR across project sets, v3 held-back, fp_val_v1 and sealed holdout
    _style_ax(ax1)
    labels = [
        "SMS\n\nn=1,162",
        "URL\n\nn=7,997",
        "Indic\n\nn=320",
        "Flow\n\nn=22.5k",
        "v3 held-\nback\nn=81",
        "fp_val\n\nn=240",
        "Sealed\n\nn=184",
    ]
    # Project sets: last bin/eval after PR #42. Holdouts/validation: main 28bdb6b (after PR #48).
    f1_vals = [0.925, 0.994, 0.969, 0.850, 0.970, 0.909, 0.813]
    # Post-PR #42 SMS dev-set FPR was not recorded, so it is plotted as "n/r" rather than guessed.
    fpr_vals = [float("nan"), 0.000, 0.031, 0.030, 0.000, 0.120, 0.300]  # SMS-route sealed FPR=0.322 annotated

    x = np.arange(len(labels))
    w = 0.36
    b1 = ax1.bar(x - w / 2, f1_vals, width=w, color=INDIGO, label="Conservative F1", zorder=3)
    b2 = ax1.bar(x + w / 2, fpr_vals, width=w, color=AMBER, label="False Positive Rate (FPR)", zorder=3)
    ax1.axvline(3.5, color="#94A3B8", linestyle="--", linewidth=0.9, zorder=2)
    ax1.text(1.5, 1.07, "Project sets (after PR #42)", ha="center", fontsize=7.6, color=SLATE, style="italic")
    ax1.text(5.0, 1.07, "Held-back / validation (after PR #48)", ha="center", fontsize=7.6, color=SLATE, style="italic")

    for b, v in zip(b1, f1_vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.018, f"{v:.3f}", ha="center", va="bottom", fontsize=7.3, color=INDIGO, fontweight="bold")
    for idx, (b, v) in enumerate(zip(b2, fpr_vals)):
        cx = b.get_x() + b.get_width() / 2
        if idx == 6:
            ax1.text(cx + 0.05, v + 0.02, "0.300\n(SMS\n0.322)", ha="center", va="bottom", fontsize=6.6, color="#B45309", fontweight="bold")
        elif np.isnan(v):
            ax1.text(cx, 0.018, "n/r", ha="center", va="bottom", fontsize=7.0, color="#B45309", fontweight="bold")
        else:
            txt = f"{v:.3f}" if v > 0 else "0"
            ax1.text(cx, v + 0.018, txt, ha="center", va="bottom", fontsize=7.0, color="#B45309", fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=7.0)
    ax1.set_ylim(0, 1.28)
    ax1.set_xlim(-0.55, 6.75)
    ax1.set_ylabel("Score / Rate", fontsize=9.5, color=SLATE)
    ax1.tick_params(axis="y", labelsize=9)
    ax1.legend(loc="upper center", ncol=2, frameon=True, facecolor="white", edgecolor=GRID, fontsize=7.6)
    ax1.set_title("A. Detection F1 vs. FPR (main 28bdb6b)", fontsize=10.0, fontweight="bold", color="#0F172A", pad=10)

    # Panel B: Galaxy S23 dumpsys meminfo PSS breakdown (KB -> MB)
    _style_ax(ax2)
    cats = ["Native Heap\n(Llama+XNNPACK)", "Private\nOther", "Graphics\n(EGL/GL)", "Code\n(.so/.apk/.jar)", "Java Heap,\nSys & Stack"]
    # dumpsys reports KiB; convert to MiB so the figure matches the GiB totals.
    kib = [1566056, 59764, 58676, 37420, 11044 + 10566 + 1316]  # App Summary rows, sum 1,744,842 KiB
    mb = [v / 1024 for v in kib]
    cols = [INDIGO, BLUE, TEAL, AMBER, SLATE]
    y = np.arange(len(cats))[::-1]
    ax2.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax2.grid(axis="y", visible=False)
    bars = ax2.barh(y, mb, height=0.58, color=cols, zorder=3)
    ax2.set_yticks(y)
    ax2.set_yticklabels(cats, fontsize=8.6)
    ax2.set_xlim(0, 1950)
    ax2.set_xlabel("Proportional Set Size — PSS (MiB)", fontsize=9.2, color=SLATE)
    ax2.tick_params(axis="x", labelsize=9)
    for b, v in zip(bars, mb):
        pct = 100.0 * v / (1744842 / 1024)
        ax2.text(v + 24, b.get_y() + b.get_height() / 2, f"{v:,.0f} MiB ({pct:.1f}%)", va="center", ha="left", fontsize=8.0, color="#0F172A", fontweight="bold")
    ax2.set_title("B. Galaxy S23 Memory Footprint (dumpsys meminfo)", fontsize=10.0, fontweight="bold", color="#0F172A", pad=10)
    ax2.text(
        0.97,
        0.07,
        "TOTAL PSS: 1,704 MiB (1.66 GiB)\nTOTAL RSS: 1,824 MiB (1.78 GiB)\nSwapPss: 23 KiB · Native Heap: 89.8%",
        transform=ax2.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.8,
        color="#1E293B",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#FEF3C7", edgecolor="#F59E0B", linewidth=0.8),
    )

    fig.tight_layout(pad=1.4)
    out = IMG_DIR / "fig-eval-summary.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return out


def build_pdf() -> None:
    if not shutil.which("pandoc") or not shutil.which("xelatex"):
        raise RuntimeError("Both pandoc and xelatex must be on PATH to build report.pdf")

    cmd = [
        "pandoc",
        str(REPORT_MD),
        "-o",
        str(REPORT_PDF),
        "--from=markdown+pipe_tables+grid_tables+fenced_code_blocks+backtick_code_blocks+yaml_metadata_block+link_attributes-implicit_figures",
        "--pdf-engine=xelatex",
        f"--include-in-header={HEADER_TEX}",
        f"--resource-path={PHASE1}:{REPO}",
        "--shift-heading-level-by=-1",
        "--number-sections",
        "-V",
        "geometry:margin=0.72in",
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
    f1 = build_arm_perf_chart()
    f2 = build_eval_and_mem_chart()
    print(f"Generated charts: {f1.relative_to(REPO)}, {f2.relative_to(REPO)}")
    build_pdf()
    verify_pdf()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
