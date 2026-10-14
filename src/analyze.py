"""
因果推断分析 v2：正面处理平行趋势违反
=====================================
v1 的伪处理时间安慰剂未通过 (beta=-1.92, p=1.4e-18)，
原因是 EMERGING 组存在与 AI 无关的技术采纳曲线（新技术栈自然上升），
导致 τbefore: 平行趋势被违反。这是真实的识别威胁，必须正面处理而非回避。

v2 的处理:
  规格族:
    (1) TWFE                        基准
    (2) TWFE + tag 线性趋势         吸收线性预趋势
    (3) TWFE + tag 二次趋势         吸收曲率预趋势
    (4) PPML                        计数因变量的正确规格
  样本族:
    A. 全样本 (11 tags)             含新兴 tag，预趋势最脏
    B. MATURE 子样本 (6 tags)       技术生命周期阶段相近，平行趋势最可信
  推断:
    - cluster-robust SE by tag
    - Rademacher wild cluster bootstrap（cluster 数仅 6/11，渐近 cluster SE 不可靠）
    - Rambachan-Roth 相对幅度敏感性分析：允许多大的预趋势违反，结论仍成立
    - 事件研究图直接展示预趋势形态
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

TREAT_QUARTER = "2022Q4"
BASE_REL = -1
N_BOOT = 2000
RNG = np.random.default_rng(20261010)

MATURE = ["python", "javascript", "java", "c#", "php", "sql"]


def qnum(q: str) -> int:
    y, qq = q.split("Q")
    return int(y) * 4 + int(qq)


def load_panel(scope: str = "all") -> pd.DataFrame:
    path = PROC / "raw_counts_tags.csv"
    if not path.exists():
        sys.exit("run src/collect.py --plan tags first")
    df = pd.read_csv(path).dropna(subset=["questions"]).drop_duplicates(
        ["unit", "quarter"], keep="last")
    df["questions"] = df["questions"].astype(int)
    intensity = json.loads((PROC / "tag_intensity.json").read_text())

    qlabels = sorted(df["quarter"].unique(), key=qnum)
    df["t"] = df["quarter"].map({q: i for i, q in enumerate(qlabels)})
    df["intensity_raw"] = df["unit"].map(intensity).astype(float)
    df["intensity"] = np.log1p(df["intensity_raw"])

    t0 = df.loc[df["quarter"] == TREAT_QUARTER, "t"].iloc[0]
    df["t0"] = t0
    df["post"] = (df["t"] >= t0).astype(int)
    df["rel"] = df["t"] - t0
    df["y_log"] = np.log1p(df["questions"])

    # 处理强度仅在组内标准化，使系数解释为「组内语料覆盖度 +1 SD」
    if scope == "mature":
        df = df[df["unit"].isin(MATURE)].copy()
    first = df.groupby("unit")["intensity"].first()
    df["I"] = (df["intensity"] - first.mean()) / first.std(ddof=1)

    # 留存 mild width：防止2021Q1之前为0的tag产生极端值
    return df.sort_values(["unit", "t"]).reset_index(drop=True)


def design(df: pd.DataFrame, trend: str, regime: str | None = None) -> pd.DataFrame:
    """构造设计矩阵。

    注意: trend 必须是 **unit-specific**（每个 tag 一条独立趋势线）。
    如果只放一个全局时间趋势 t，它会被 quarter FE 完全吸收、
    对 beta 毫无影响（这正是 v1 里三种 trend 规格得到同一个
    beta=-1.957 的原因）。要吸收预趋势，必须是 tag × t 交互。
    """
    d = df.copy()
    if regime:
        lo, hi = regime
        d = d[(d["rel"] >= lo) & (d["rel"] <= hi)].copy()
    X = pd.DataFrame(index=d.index)
    X["did"] = d["I"] * d["post"]
    if trend in ("linear", "quad"):
        for u in d["unit"].unique():
            X[f"trl_{u}"] = (d["unit"] == u).astype(float) * d["t"]
    if trend == "quad":
        for u in d["unit"].unique():
            X[f"trq_{u}"] = (d["unit"] == u).astype(float) * d["t"] ** 2
    X = pd.concat([X,
                   pd.get_dummies(d["unit"], prefix="u", drop_first=True).astype(float),
                   pd.get_dummies(d["t"], prefix="t", drop_first=True).astype(float)], axis=1)
    return sm.add_constant(X).astype(float)


def fit(df: pd.DataFrame, ycol: str, trend: str, regime: str | None = None):
    d = df.copy()
    if regime:
        lo, hi = regime
        d = d[(d["rel"] >= lo) & (d["rel"] <= hi)].copy()
    X = design(d, trend)
    y = d[ycol].astype(float)
    m = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": d["unit"]})
    ci = m.conf_int().loc["did"]
    return {"beta": float(m.params["did"]), "se": float(m.bse["did"]),
            "p": float(m.pvalues["did"]), "ci": [float(ci[0]), float(ci[1])],
            "nobs": int(m.nobs)}


def wild_bootstrap(df: pd.DataFrame, ycol: str, trend: str = "linear",
                   regime: str | None = None, B: int = N_BOOT) -> dict:
    """Rademacher wild cluster bootstrap。
    p 值用受限模型残差（零假设下正确）；CI 用非受限残差并以 beta_hat 中心化。"""
    d = df.copy()
    if regime:
        lo, hi = regime
        d = d[(d["rel"] >= lo) & (d["rel"] <= hi)].copy()
    X = design(d, trend)
    y = d[ycol].astype(float).values
    Xm = X.values
    pos = list(X.columns).index("did")
    units = sorted(d["unit"].unique())
    uarr = d["unit"].values

    beta_hat = sm.OLS(y, Xm).fit().params[pos]

    keep = [i for i in range(Xm.shape[1]) if i != pos]
    rest = sm.OLS(y, Xm[:, keep]).fit()
    full = sm.OLS(y, Xm).fit()

    def draw(fitted, resid):
        wmap = dict(zip(units, RNG.choice([-1.0, 1.0], size=len(units))))
        return fitted + np.array([wmap[u] for u in uarr]) * resid

    b0 = np.empty(B)
    for b in range(B):
        b0[b] = sm.OLS(draw(rest.fittedvalues, rest.resid), Xm).fit().params[pos]
    p = float((1 + 2 * min((b0 <= beta_hat).sum(), (b0 >= beta_hat).sum())) / (B + 1))

    b1 = np.empty(B)
    for b in range(B):
        b1[b] = sm.OLS(draw(full.fittedvalues, full.resid), Xm).fit().params[pos]
    lo = float(2 * beta_hat - np.percentile(b1, 97.5))
    hi = float(2 * beta_hat - np.percentile(b1, 2.5))
    return {"beta": float(beta_hat), "p_wild": min(p, 1.0), "ci_wild": [lo, hi], "B": B}


def ppml(df: pd.DataFrame, trend: str = "linear", regime: str | None = None) -> dict:
    d = df.copy()
    if regime:
        lo, hi = regime
        d = d[(d["rel"] >= lo) & (d["rel"] <= hi)].copy()
    X = design(d, trend)
    m = sm.GLM(d["questions"].astype(float), X, family=sm.families.Poisson()).fit(
        cov_type="cluster", cov_kwds={"groups": d["unit"]})
    ci = m.conf_int().loc["did"]
    return {"beta": float(m.params["did"]), "irr": float(np.exp(m.params["did"])),
            "p": float(m.pvalues["did"]), "ci": [float(ci[0]), float(ci[1])]}


def placebo(df: pd.DataFrame, lead: int, ycol: str = "y_log", trend: str = "linear") -> dict:
    """伪处理时间：处理时点前移 lead 期，样本截断以排除真实处理期。"""
    d = df.copy()
    d = d[d["rel"] < lead].copy()          # 只看伪处理窗口内
    t0 = int(d["t0"].iloc[0]) - lead
    d["post"] = (d["t"] >= t0).astype(int)
    d["rel"] = d["t"] - t0
    return fit(d, ycol, trend)


def honest_did(df: pd.DataFrame, ycol: str = "y_log", trend: str = "quad") -> dict:
    """Rambachan-Roth (2023) 相对幅度敏感性分析的线性外推近似。
    问：允许预趋势违反到什么程度（相对于处理后斜率的 κ 倍），结论仍符号稳健？
    """
    es = event_study(df, ycol, trend)
    pre = es[(es["rel"] < -1)]
    post_cnt = len(es[es["rel"] >= 0])
    if pre.empty or post_cnt == 0:
        return {}
    a_max = float(pre["beta"].abs().max())          # 预趋势最大违反
    mdl = fit(df, ycol, trend)
    beta, se = mdl["beta"], mdl["se"]
    tcrit = 1.96
    K = post_cnt - 1
    # breakdown κ*: 使识别区间触及 0 的相对幅度
    kappa_star = (abs(beta) - tcrit * se) / (a_max * K) if a_max * K > 0 else np.inf
    return {"beta": beta, "se": se, "max_pre_violation": a_max,
            "post_periods": post_cnt, "breakdown_kappa": float(kappa_star),
            "interp": ("结论可容忍的最大预趋势违反 = 处理后斜率的 %.2f 倍"
                       % kappa_star) if np.isfinite(kappa_star) else "n/a"}


def event_study(df: pd.DataFrame, ycol: str = "y_log", trend: str = "linear") -> pd.DataFrame:
    rels = sorted(df["rel"].unique())
    rows = []
    for k in rels:
        if k == BASE_REL:
            rows.append({"rel": int(k), "beta": 0.0, "se": 0.0, "ci_lo": 0.0, "ci_hi": 0.0})
            continue
        d = df.copy()
        X = pd.DataFrame(index=d.index)
        X["did"] = (d["rel"] == k).astype(float) * d["I"]
        if trend in ("linear", "quad"):
            for u in d["unit"].unique():
                X[f"trl_{u}"] = (d["unit"] == u).astype(float) * d["t"]
        if trend == "quad":
            for u in d["unit"].unique():
                X[f"trq_{u}"] = (d["unit"] == u).astype(float) * d["t"] ** 2
        X = pd.concat([X,
                       pd.get_dummies(d["unit"], prefix="u", drop_first=True).astype(float),
                       pd.get_dummies(d["t"], prefix="t", drop_first=True).astype(float)], axis=1)
        Xv = sm.add_constant(X).astype(float)
        m = sm.OLS(d[ycol].astype(float), Xv).fit(
            cov_type="cluster", cov_kwds={"groups": d["unit"]})
        ci = m.conf_int().loc["did"]
        rows.append({"rel": int(k), "beta": float(m.params["did"]),
                     "se": float(m.bse["did"]), "ci_lo": float(ci[0]), "ci_hi": float(ci[1])})
    return pd.DataFrame(rows).sort_values("rel").reset_index(drop=True)


def cross_site() -> pd.DataFrame:
    """跨站点验证：2022Q3(处理前) vs 2023Q4(处理后)，6 个 Stack Exchange 站点。"""
    f = PROC / "sitewide_check.csv"
    if not f.exists():
        return pd.DataFrame()
    d = pd.read_csv(f)
    d["quarter"] = d["quarter"].astype(str)
    w = d.pivot_table(index="site", columns="quarter", values="sitewide_questions")
    if "2022Q3" not in w or "2023Q4" not in w:
        return pd.DataFrame()
    w["pre"] = w["2022Q3"]
    w["post"] = w["2023Q4"]
    w["pct_change"] = (w["post"] - w["pre"]) / w["pre"]
    return w.reset_index().sort_values("pct_change")


def main():
    report = {"specs": {}, "placebo": {}, "event_study": {}, "honest_did": {}, "cross_site": {}}

    for scope, df in [("all_11tags", load_panel("all")),
                      ("mature_6tags", load_panel("mature"))]:
        for trend in ["none", "linear", "quad"]:
            report["specs"][f"{scope}|OLS|trend={trend}"] = fit(df, "y_log", trend)
        report["specs"][f"{scope}|PPML|trend=linear"] = ppml(df, "linear")
        report["specs"][f"{scope}|PPML|trend=quad"] = ppml(df, "quad")

        report["placebo"]["%s|OLS|trend=linear" % scope] = placebo(df, lead=2, trend="linear")
        report["placebo"]["%s|OLS|trend=quad" % scope] = placebo(df, lead=2, trend="quad")
        report["honest_did"][scope] = honest_did(df)
        report["event_study"][scope] = event_study(df, "y_log", "quad").to_dict("records")

    # 有限 Wild bootstrap 推断（关键规格）
    for scope in ["all_11tags", "mature_6tags"]:
        df = load_panel("mature" if scope == "mature_6tags" else "all")
        report.setdefault("wild", {})[f"{scope}|trend=quad"] = wild_bootstrap(df, "y_log", "quad")

    cs = cross_site()
    if not cs.empty:
        report["cross_site"] = cs.round(4).to_dict("records")

    (OUT / "results.json").write_text(json.dumps(report, indent=2, default=float))

    print("\n=== SPECS ===")
    for k, v in report["specs"].items():
        extra = f"  IRR={v['irr']:.3f}" if "irr" in v else ""
        print(f"{k:44s} beta={v['beta']:+.3f}  p={v['p']:.4f}{extra}")
    print("\n=== PLACEBO (处理时点前移 2 期) ===")
    for k, v in report["placebo"].items():
        print(f"{k:44s} beta={v['beta']:+.3f}  p={v['p']:.4f}")
    print("\n=== WILD BOOTSTRAP ===")
    for k, v in report.get("wild", {}).items():
        print(f"{k:42s} beta={v['beta']:+.3f}  p_wild={v['p_wild']:.4f}  "
              f"CI=[{v['ci_wild'][0]:.3f},{v['ci_wild'][1]:.3f}]")
    print("\n=== HONEST DID ===")
    for k, v in report["honest_did"].items():
        print(f"{k:42s} beta={v.get('beta', float('nan')):+.3f}  "
              f"breakdown_kappa={v.get('breakdown_kappa', float('nan')):.2f}")
    print("\n=== CROSS-SITE ===")
    for r in report.get("cross_site", []):
        print(f"{r['site']:14s} {int(r['pre']):>7,} -> {int(r['post']):>7,}  {r['pct_change']:+.3f}")


if __name__ == "__main__":
    main()
