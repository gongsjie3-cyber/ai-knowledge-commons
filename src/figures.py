"""生成全部图表。图注用英文，便于直接放入 portfolio / 论文 working paper。"""

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
from analyze import load_panel, cross_site, qnum, MATURE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "outputs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5,
    "font.family": "DejaVu Sans",
})

C_TREAT = "#993C1D"
C_CTRL = "#185FA5"
C_GRAY = "#888780"
C_ACC = "#0F6E56"

GROUP_COLOR = {"MATURE": C_TREAT, "EMERGING": C_CTRL, "NATIVE_AI": C_ACC}


def fig_event_study():
    import statsmodels.api as sm
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=False)

    for ax, (scope, title) in zip(axes, [("all", "All tags (n=11)"),
                                         ("mature", "Mature tags only (n=6)")]):
        df = load_panel(scope)
        from analyze import event_study
        es = event_study(df, "y_log", "quad")
        r = es["rel"].values
        b = es["beta"].values
        lo, hi = es["ci_lo"].values, es["ci_hi"].values
        ax.axhline(0, color=C_GRAY, lw=0.7)
        ax.axvline(-0.5, color=C_TREAT, lw=0.9, ls="--")
        ax.plot(r, b, "o-", color=C_CTRL, ms=3.2, lw=1.2)
        ax.fill_between(r, lo, hi, color=C_CTRL, alpha=0.15, lw=0)
        ax.set_title(f"{title}\nunit-specific quadratic trends absorbed", fontsize=9)
        ax.set_xlabel("quarters relative to ChatGPT release (2022Q4 = 0)")
        ax.set_ylabel("effect per +1 SD corpus coverage")

    fig.suptitle("Event study: once each knowledge domain's own trend is absorbed, "
                 "the corpus-coverage gradient vanishes", fontsize=10, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_event_study.png", bbox_inches="tight")
    plt.close(fig)


def fig_trajectories():
    df = load_panel("all")
    df = df.sort_values("t")
    fig, ax = plt.subplots(figsize=(9.6, 3.8))
    base = df[df["rel"] == -1].set_index("unit")["questions"]
    for unit, g in df.groupby("unit"):
        grp = g["group"].iloc[0]
        y = g.sort_values("t")["questions"].values / float(base[unit]) * 100
        x = g.sort_values("t")["rel"].values
        lw = 1.6 if grp == "MATURE" else 1.2
        ls = "-" if grp == "MATURE" else "--"
        ax.plot(x, y, ls, lw=lw, color=GROUP_COLOR[grp], alpha=0.85, label=None)
        ax.text(x[-1] + 0.25, max(y[-1], 0.6), unit, fontsize=7,
                color=GROUP_COLOR[grp])
    ax.axvline(-0.5, color=C_TREAT, lw=1.0, ls="--")
    ax.axhline(100, color=C_GRAY, lw=0.7)
    ax.set_yscale("log")
    ax.set_xlim(-8.5, 18)
    ax.set_xlabel("quarters relative to ChatGPT release")
    ax.set_ylabel("questions, indexed to 2022Q3 = 100 (log scale)")
    handles = [plt.Line2D([], [], color=c, lw=1.6, label=l)
               for l, c in [("Mature (high corpus)", C_TREAT),
                            ("Emerging (near-zero corpus)", C_CTRL),
                            ("AI-native topics", C_ACC)]]
    ax.legend(handles=handles, fontsize=8, frameon=False, loc="lower left")
    ax.set_title("Every domain collapses, including ones LLMs have minimal training data on — "
                 "so the late-stage collapse is NOT an AI story", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_trajectories.png", bbox_inches="tight")
    plt.close(fig)


def fig_cross_site():
    cs = cross_site()
    if cs.empty:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for _, r in cs.iterrows():
        pre, post = r["pre"], r["post"]
        is_so = r["site"] == "stackoverflow"
        ax.plot([0, 1], [pre / pre * 100, post / pre * 100], "-o",
                color=C_TREAT if is_so else C_CTRL,
                lw=2.2 if is_so else 1.1,
                ms=5 if is_so else 3.5,
                alpha=1.0 if is_so else 0.75)
        ax.text(1.05, post / pre * 100, f"{r['site']}  {r['pct_change']*100:+.1f}%",
                fontsize=8, va="center", color=C_TREAT if is_so else C_CTRL,
                weight="500" if is_so else "400")
    ax.axhline(100, color=C_GRAY, lw=0.7, ls=":")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["2022Q3\n(pre-ChatGPT)", "2023Q4\n(+13 months)"])
    ax.set_xlim(-0.15, 1.9)
    ax.set_ylabel("questions, indexed to 2022Q3 = 100")
    ax.set_title("Cross-site slope: the drop is ordered exactly by how well\n"
                 "an LLM can substitute for that domain — math (needs formal\n"
                 "proof) barely moves, programming collapses", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_cross_site.png", bbox_inches="tight")
    plt.close(fig)


def fig_attribution():
    """核心图：把总降幅分解为「AI 可归因」与「平台级衰亡」。"""
    f = Path(__file__).resolve().parent.parent / "data" / "processed" / "sitewide_check.csv"
    if not f.exists():
        return
    d = pd.read_csv(f)
    w = d.pivot_table(index="site", columns="quarter", values="sitewide_questions")
    order = ["2022Q3", "2023Q1", "2023Q4", "2024Q4", "2025Q4", "2026Q3"]
    order = [q for q in order if q in w.columns]
    so = w.loc["stackoverflow", order].astype(float)
    ma = w.loc["math", order].astype(float)
    base_so, base_ma = so.iloc[0], ma.iloc[0]
    tot = (so - base_so) / base_so * 100          # SO 总降幅 (pp)
    ctrl = (ma - base_ma) / base_ma * 100         # 对照组降幅 (pp)
    ai = tot - ctrl                                # DiD = AI 可归因
    x = np.arange(len(order))

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.6),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    ax.bar(x, ai, 0.42, label="Attributable to GenAI substitution (DiD vs math)",
           color=C_TREAT, zorder=3)
    ax.bar(x, ctrl, 0.42, bottom=ai, label="Platform-wide decline (seen even where LLMs fail)",
           color=C_GRAY, zorder=3)
    for i, (a, t) in enumerate(zip(ai, tot)):
        ax.text(i, t - 3.5, f"{t:.0f}%", ha="center", fontsize=7.5, color="#2C2C2A")
        if i > 0:
            ax.text(i, a / 2, f"{a:.0f}pp", ha="center", fontsize=7.5,
                    color="white", weight="500")
    ax.set_xticks(x)
    ax.set_xticklabels(order, fontsize=8)
    ax.axhline(0, color="#444441", lw=0.8)
    ax.set_ylabel("change vs 2022Q3 (percentage points)")
    ax.legend(fontsize=7.5, frameon=False, loc="lower left")
    ax.set_title("Decomposing the collapse: what share is actually the AI's fault?",
                 fontsize=9.5)

    ax = axes[1]
    share = np.where(np.abs(tot) > 1e-9, ai / tot * 100, np.nan)
    ax.plot(x, share, "o-", color=C_TREAT, lw=1.8, ms=5)
    ax.set_ylim(-5, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(order, fontsize=8)
    ax.axhline(50, color=C_GRAY, lw=0.6, ls=":")
    ax.set_ylabel("share of the drop attributable to GenAI (%)")
    ax.set_title("GenAI's explanatory share peaks then is diluted away",
                 fontsize=9.5)
    for i, s in enumerate(share):
        ax.text(i, s + 6, f"{s:.0f}%", ha="center", fontsize=8, color=C_TREAT)

    fig.tight_layout()
    fig.savefig(FIG / "fig4_attribution.png", bbox_inches="tight")
    plt.close(fig)

    return {"quarters": order, "so_total_pct": tot.round(2).tolist(),
            "ctrl_pct": ctrl.round(2).tolist(), "did_pp": ai.round(2).tolist(),
            "ai_share_pct": np.round(share, 2).tolist()}


def fig_threshold():
    """剂量-反应：门槛效应而非连续梯度。
    基数太小的 tag（baseline < 100）百分比变化不可靠，剔除并在注中说明。"""
    import statsmodels.api as sm
    df = load_panel("all")
    base = df[df["rel"] == -1].set_index("unit")["questions"]
    window = df[(df["rel"] >= 0) & (df["rel"] <= 4)]
    post = window.groupby("unit")["questions"].mean()
    inten = df.groupby("unit")["intensity_raw"].first()
    grp = df.groupby("unit")["group"].first()

    keep = base[base >= 100].index
    chg = ((post - base) / base * 100).loc[keep].dropna()
    excluded = sorted(set(base.index) - set(keep))

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.5))
    ax = axes[0]
    for unit in chg.index:
        ax.scatter(inten[unit], chg[unit], s=52, color=GROUP_COLOR[grp[unit]],
                   zorder=3, edgecolor="white", linewidth=0.8)
        ax.text(inten[unit], chg[unit] + 5, unit, fontsize=7, ha="center")
    ax.set_xscale("symlog", linthresh=100)
    ax.axhline(chg.mean(), color=C_GRAY, lw=0.7, ls=":",
               label=f"mean = {chg.mean():.1f}%")
    ax.set_xlabel("corpus coverage: cumulative questions before ChatGPT (symlog)")
    ax.set_ylabel("avg change, 2022Q3 -> next 5 quarters (%)")
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("No gradient: domains differing 1,000x in corpus coverage\n"
                 "all land in a narrow band", fontsize=9.5)
    ax.text(0.02, 0.02,
            "excluded (baseline < 100, pct-change unreliable): " + ", ".join(excluded),
            transform=ax.transAxes, fontsize=6.5, color=C_GRAY)

    ax = axes[1]
    m = df[df["unit"].isin(MATURE)]
    b6 = base[base.index.isin(MATURE)]
    p6 = window.groupby("unit")["questions"].mean()[MATURE]
    y6 = ((p6 - b6) / b6 * 100).values
    x6 = np.log1p(inten[MATURE].values)
    o = np.argsort(x6)
    ax.scatter(x6, y6, s=55, color=C_TREAT, zorder=3, edgecolor="white", linewidth=0.8)
    for xx, yy, lab in zip(x6, y6, MATURE):
        ax.text(xx, yy + 1.2, lab, fontsize=7, ha="center")
    Xr = sm.add_constant(x6)
    res = sm.OLS(y6, Xr).fit()
    xs = np.linspace(x6.min(), x6.max(), 50)
    preds = res.get_prediction(sm.add_constant(xs))
    ax.plot(xs, preds.predicted_mean, color=C_TREAT, lw=1.4)
    ax.fill_between(xs, preds.conf_int()[:, 0], preds.conf_int()[:, 1],
                    color=C_TREAT, alpha=0.15, lw=0)
    ax.set_xlabel("log corpus coverage (within mature domains)")
    ax.set_ylabel("avg change (%)")
    ax.set_title(f"Within mature domains the slope is flat:\n"
                 f"b = {res.params[1]:+.2f} pp per log point  (p = {res.pvalues[1]:.2f})",
                 fontsize=9.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig5_threshold.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_event_study()
    fig_trajectories()
    fig_cross_site()
    attribution = fig_attribution()
    fig_threshold()
    if attribution:
        (ROOT / "outputs" / "attribution.json").write_text(json.dumps(attribution, indent=2))
    print("figures ->", sorted(p.name for p in FIG.glob("*.png")))
    if attribution:
        print(json.dumps(attribution, indent=2))
