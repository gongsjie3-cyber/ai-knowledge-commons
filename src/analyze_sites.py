"""
跨站点面板的正式识别（v2 升级）
================================
v1 只有 6 站点 x 2 期，只能做描述性双期 DiD。
本次补齐 8 站点 x 23 季度的完整面板后，可以做真正的面板识别。

识别设计:
  以 Mathematics 为 numeraire（基准组）—— 理由不是"它没被 AI 影响"，
  而是它代表了「LLM 因无法产出严格形式证明而难以替代的知识领域」，
  可作为反事实锚点。对除 math 外的 7 个站点构造：

      D_st = log(Y_st) - log(Y_math,t)

  差分后所有时间层面的共同冲击（平台政策、季节、宏观）被自动吸收，
  剩下的是各领域相对形式证明领域的超额变动。

      D_st = alpha_s + sum_k beta_k * 1[rel_t = k] + eps_st

  这样处理组有 7 个单元（而非 1 个），cluster 数从 2 提升到 7，
  wild cluster bootstrap 的有限样本性质大幅改善。

  注意：beta 是「相对于基准组的平均处理效应」，
  异质性通过分站点单独报告。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
FIG = OUT / "figures"

TREAT_QUARTER = "2022Q4"
BASE_REL = -1
N_BOOT = 2000
RNG = np.random.default_rng(20261011)
NUMERAIRE = "math"


def qnum(q: str) -> int:
    y, qq = q.split("Q")
    return int(y) * 4 + int(qq)


def load_site_panel() -> pd.DataFrame:
    path = PROC / "raw_counts_sites.csv"
    if not path.exists():
        raise SystemExit("no site panel found; run: python src/collect.py --plan sites")
    df = pd.read_csv(path)
    df = df[["site", "quarter", "questions"]].copy()
    chk = PROC / "sitewide_check.csv"
    if chk.exists():                       # 合并早期稀疏验证点（完整面板优先）
        c = pd.read_csv(chk).rename(columns={"sitewide_questions": "questions"})
        df = pd.concat([df, c[["site", "quarter", "questions"]]], ignore_index=True)
    df = df.dropna(subset=["questions"])
    df = df.drop_duplicates(["site", "quarter"], keep="first").reset_index(drop=True)
    df["questions"] = df["questions"].astype(float)

    qlabels = sorted(df["quarter"].unique(), key=qnum)
    df["t"] = df["quarter"].map({q: i for i, q in enumerate(qlabels)})
    t0 = df.loc[df["quarter"] == TREAT_QUARTER, "t"].iloc[0]
    df["post"] = (df["t"] >= t0).astype(int)
    df["rel"] = df["t"] - t0
    return df.sort_values(["site", "t"]).reset_index(drop=True)


def relative_panel(df: pd.DataFrame) -> pd.DataFrame:
    w = df.pivot_table(index="t", columns="site", values="questions")
    base = w[NUMERAIRE]
    rel = np.log(w.div(base, axis=0)).drop(columns=[NUMERAIRE])
    long = rel.stack().rename("dlog").reset_index()
    long.columns = ["t", "site", "dlog"]
    meta = df[["t", "quarter", "post", "rel"]].drop_duplicates("t")
    long = long.merge(meta, on="t", how="left")
    return long.sort_values(["site", "t"]).reset_index(drop=True)


def _X(d: pd.DataFrame, trend: str, did_col: pd.Series | None = None):
    X = pd.DataFrame(index=d.index)
    if did_col is not None:
        X["did"] = did_col
    if trend == "linear":
        for u in d["site"].unique():
            X[f"trl_{u}"] = (d["site"] == u).astype(float) * d["t"]
    X = pd.concat([X, pd.get_dummies(d["site"], prefix="s", drop_first=True).astype(float)], axis=1)
    return sm.add_constant(X).astype(float)


def fit(d: pd.DataFrame, ycol: str, trend: str = "none", did_col=None):
    X = _X(d, trend, did_col if did_col is not None else d["post"].astype(float))
    m = sm.OLS(d[ycol].astype(float), X).fit(
        cov_type="cluster", cov_kwds={"groups": d["site"]})
    ci = m.conf_int().loc["did"]
    return {"beta": float(m.params["did"]), "se": float(m.bse["did"]),
            "p": float(m.pvalues["did"]), "ci": [float(ci[0]), float(ci[1])],
            "nobs": int(m.nobs), "n_clusters": int(d["site"].nunique())}


def wild_bootstrap(d: pd.DataFrame, ycol: str, trend: str = "none", B: int = N_BOOT):
    X = _X(d, trend, d["post"].astype(float))
    y = d[ycol].astype(float).values
    Xm = X.values
    pos = list(X.columns).index("did")
    units = sorted(d["site"].unique())
    uarr = d["site"].values
    beta_hat = sm.OLS(y, Xm).fit().params[pos]
    keep = [i for i in range(Xm.shape[1]) if i != pos]
    rest = sm.OLS(y, Xm[:, keep]).fit()
    full = sm.OLS(y, Xm).fit()

    def draw(f, r):
        wmap = dict(zip(units, RNG.choice([-1.0, 1.0], size=len(units))))
        return f + np.array([wmap[u] for u in uarr]) * r

    b0 = np.array([sm.OLS(draw(rest.fittedvalues, rest.resid), Xm).fit().params[pos]
                   for _ in range(B)])
    p = float((1 + 2 * min((b0 <= beta_hat).sum(), (b0 >= beta_hat).sum())) / (B + 1))
    b1 = np.array([sm.OLS(draw(full.fittedvalues, full.resid), Xm).fit().params[pos]
                   for _ in range(B)])
    return {"beta": float(beta_hat), "p_wild": min(p, 1.0),
            "ci_wild": [float(2 * beta_hat - np.percentile(b1, 97.5)),
                        float(2 * beta_hat - np.percentile(b1, 2.5))], "B": B}


def event_study(d: pd.DataFrame, ycol: str = "dlog", trend: str = "none") -> pd.DataFrame:
    rows = []
    for k in sorted(d["rel"].unique()):
        if k == BASE_REL:
            rows.append({"rel": int(k), "beta": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "se": 0.0})
            continue
        col = (d["rel"] == k).astype(float)
        X = _X(d, trend, col)
        m = sm.OLS(d[ycol].astype(float), X).fit(
            cov_type="cluster", cov_kwds={"groups": d["site"]})
        ci = m.conf_int().loc["did"]
        rows.append({"rel": int(k), "beta": float(m.params["did"]),
                     "se": float(m.bse["did"]),
                     "ci_lo": float(ci[0]), "ci_hi": float(ci[1])})
    return pd.DataFrame(rows).sort_values("rel").reset_index(drop=True)


def placebo(d: pd.DataFrame, lead: int = 2, trend: str = "none"):
    dd = d[d["rel"] < lead].copy()
    t0 = int(dd.loc[dd["t"].notna(), "t"].min())
    # 伪处理起点：真实起点前移 lead 期
    real_t0 = int(d.loc[d["rel"] == 0, "t"].iloc[0])
    dd["post"] = (dd["t"] >= real_t0 - lead).astype(int)
    return fit(dd, "dlog", trend, dd["post"].astype(float))


def per_site_att(df: pd.DataFrame) -> pd.DataFrame:
    """各站点在关键窗口内的相对降幅（vs numeraire）。"""
    w = df.pivot_table(index="t", columns="site", values="questions")
    t0 = df.loc[df["quarter"] == TREAT_QUARTER, "t"].iloc[0]
    pre = df.loc[df["t"] == t0 - 1, ["site", "questions"]].set_index("site")["questions"]
    rows = []
    for q in ["2023Q1", "2023Q4", "2024Q4", "2025Q4", "2026Q3"]:
        if q not in df["quarter"].values:
            continue
        cur = df.loc[df["quarter"] == q, ["site", "questions"]].set_index("site")["questions"]
        for s in w.columns:
            if s not in cur.index or s not in pre.index:
                continue
            d_s = (cur[s] - pre[s]) / pre[s] * 100
            d_m = (cur[NUMERAIRE] - pre[NUMERAIRE]) / pre[NUMERAIRE] * 100
            rows.append({"site": s, "quarter": q, "own_pct": d_s,
                         "numeraire_pct": d_m, "did_pp": d_s - d_m})
    return pd.DataFrame(rows)


def main():
    df = load_site_panel()
    d = relative_panel(df)
    print(f"site panel: {df['site'].nunique()} sites x {df['t'].nunique()} quarters "
          f"= {len(df)} obs; relative panel n={len(d)}")

    res = {
        "n_obs_site_panel": len(df),
        "sites": sorted(df["site"].unique().tolist()),
        "numeraire": NUMERAIRE,
        "did_pooled": fit(d, "dlog", "none"),
        "did_pooled_trend": fit(d, "dlog", "linear"),
        "wild": wild_bootstrap(d, "dlog", "none"),
        "placebo": placebo(d, lead=2),
        "event_study": event_study(d).to_dict("records"),
        "per_site_att": per_site_att(df).round(3).to_dict("records"),
    }
    (OUT / "results_sites.json").write_text(json.dumps(res, indent=2, default=float))

    print("\n=== POOLED DiD (relative to Mathematics) ===")
    for k in ["did_pooled", "did_pooled_trend"]:
        v = res[k]
        print(f"{k:20s} beta={v['beta']:+.3f}  se={v['se']:.3f}  p={v['p']:.4f}  "
              f"clusters={v['n_clusters']}")
    w = res["wild"]
    print(f"wild bootstrap       beta={w['beta']:+.3f}  p={w['p_wild']:.4f}  "
          f"CI=[{w['ci_wild'][0]:.3f},{w['ci_wild'][1]:.3f}]")
    pl = res["placebo"]
    print(f"placebo (lead 2)     beta={pl['beta']:+.3f}  p={pl['p']:.4f}")

    print("\n=== PER-SITE ATT (percentage points vs Mathematics) ===")
    piv = per_site_att(df).pivot_table(index="site", columns="quarter", values="did_pp")
    print(piv.round(1).to_string())
    return res


if __name__ == "__main__":
    main()
