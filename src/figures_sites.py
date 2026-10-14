"""跨站点面板的图表：横截面一致性证据。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_sites import load_site_panel, per_site_att, relative_panel, event_study  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "outputs" / "figures"
OUT = ROOT / "outputs"

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "font.family": "DejaVu Sans",
})

C_SO = "#A32D2D"
C_OTHER = "#185FA5"
C_GRAY = "#888780"


def fig_site_att():
    """核心图：7 个知识领域相对数学站点的超额下降，全部同时触底后收敛。"""
    df = load_site_panel()
    att = per_site_att(df)
    piv = att.pivot_table(index="site", columns="quarter", values="did_pp")
    order = ["2023Q1", "2023Q4", "2024Q4", "2025Q4", "2026Q3"]
    piv = piv[[q for q in order if q in piv.columns]]

    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    x = np.arange(len(piv.columns))
    for site in piv.index:
        if site == "math":
            continue
        is_so = site == "stackoverflow"
        ax.plot(x, piv.loc[site].values, "-o",
                color=C_SO if is_so else C_OTHER,
                lw=2.4 if is_so else 1.1,
                ms=5.5 if is_so else 3.5,
                alpha=1.0 if is_so else 0.65, zorder=4 if is_so else 3)
        ax.annotate(site, (x[-1], piv.loc[site].values[-1]),
                    fontsize=7.5, xytext=(4, 0), textcoords="offset points",
                    color=C_SO if is_so else C_OTHER, va="center")
    ax.axhline(0, color="#444441", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(piv.columns, fontsize=8)
    ax.set_xlim(-0.4, len(piv.columns) - 1 + 0.9)
    ax.set_ylabel("excess decline vs Mathematics (percentage points)")
    ax.set_title("Seven independent knowledge domains all bottom out at the same\n"
                 "quarter and then converge back to zero: the AI shock is a\n"
                 "one-off level shift, not a persistent growth-rate change",
                 fontsize=9.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig6_site_att.png", bbox_inches="tight")
    plt.close(fig)
    return {"quarters": list(piv.columns),
            "did_pp": {s: piv.loc[s].round(2).tolist() for s in piv.index}}


def fig_site_trajectories():
    """8 站点原始轨迹（指数化至 2022Q3）。"""
    df = load_site_panel()
    w = df.pivot_table(index="t", columns="site", values="questions")
    qlab = df.drop_duplicates("t").set_index("t")["quarter"]
    t0 = int(df.loc[df["quarter"] == "2022Q4", "t"].iloc[0])
    base_idx = t0 - 1
    rel = df.drop_duplicates("t").set_index("t")["rel"]

    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    xs = rel.sort_index().values
    entries = []
    for s in w.columns:
        y = w[s].values / w[s].values[base_idx] * 100
        is_so = s == "stackoverflow"
        is_math = s == "math"
        ax.plot(xs, y, lw=2.4 if is_so else (2.0 if is_math else 1.0),
                color=C_SO if is_so else ("#0F6E56" if is_math else C_OTHER),
                alpha=1.0 if (is_so or is_math) else 0.55, zorder=4 if (is_so or is_math) else 3)
        entries.append({"site": s, "y": float(y[-1]),
                        "color": C_SO if is_so else ("#0F6E56" if is_math else C_OTHER),
                        "bold": is_so or is_math})
    # 标签防重叠：除 stackoverflow 外所有站点末期都落在 5-12 的窄带里，
    # 在 log10 空间自上而下强制最小间距。
    entries.sort(key=lambda e: -np.log10(e["y"]))
    min_gap = 0.14
    lys = [np.log10(e["y"]) for e in entries]
    for i in range(1, len(lys)):
        if lys[i - 1] - lys[i] < min_gap:
            lys[i] = lys[i - 1] - min_gap
    for e, ly in zip(entries, lys):
        ax.annotate(e["site"], (xs[-1], 10 ** ly), fontsize=7.5,
                    xytext=(4, 0), textcoords="offset points",
                    va="center", color=e["color"],
                    weight="500" if e["bold"] else "400")
    ax.set_yscale("log")
    ax.axvline(-0.5, color=C_SO, lw=1.0, ls="--")
    ax.axhline(100, color=C_GRAY, lw=0.7, ls=":")
    ax.set_xlim(-8.5, 16.5)
    ax.set_xlabel("quarters relative to ChatGPT release (0 = 2022Q4)")
    ax.set_ylabel("questions, indexed to 2022Q3 = 100 (log scale)")
    ax.set_title("Every Stack Exchange site collapses; Mathematics lags by roughly\n"
                 "a year, then catches up — the late collapse is not domain-specific",
                 fontsize=9.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig7_site_trajectories.png", bbox_inches="tight")
    plt.close(fig)


def fig_site_event_study():
    """以数学站点为基准的面板事件研究。"""
    df = load_site_panel()
    d = relative_panel(df)
    for trend, name in [("none", "no site-specific trend"),
                        ("linear", "site-specific linear trend")]:
        es = event_study(d, "dlog", trend)
        fig, ax = plt.subplots(figsize=(6.4, 3.2))
        r = es["rel"].values
        ax.axhline(0, color=C_GRAY, lw=0.7)
        ax.axvline(-0.5, color=C_SO, lw=0.9, ls="--")
        ax.plot(r, es["beta"].values, "o-", color=C_OTHER, ms=3.2, lw=1.2)
        ax.fill_between(r, es["ci_lo"].values, es["ci_hi"].values,
                        color=C_OTHER, alpha=0.15, lw=0)
        ax.set_xlabel("quarters relative to ChatGPT release")
        ax.set_ylabel("excess log change vs Mathematics")
        ax.set_title(f"Panel event study, numeraire = Mathematics\n({name})", fontsize=9.5)
        fig.tight_layout()
        fig.savefig(FIG / f"fig8_event_study_{trend}.png", bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    att = fig_site_att()
    fig_site_trajectories()
    fig_site_event_study()
    if att:
        (OUT / "site_att.json").write_text(json.dumps(att, indent=2))
    print("done:", sorted(p.name for p in FIG.glob("*.png")))
    print(json.dumps(att, indent=2))
