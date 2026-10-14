"""
发布前审计：用原始数据重算报告中出现的每一个数字。
目的不是再跑一遍分析，而是逐条核对「写给人看的数字」是否与数据一致，
尤其是检查不同口径是否给出相互矛盾的结论。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

FAIL = []
WARN = []


def check(label, claimed, actual, tol=0.05, scale=1.0):
    ok = abs(claimed * scale - actual * scale) <= tol
    print(f"{'OK ' if ok else 'FAIL'} {label:52s} claimed={claimed:>9.3f} actual={actual:>9.3f}")
    if not ok:
        FAIL.append(f"{label}: claimed {claimed} vs actual {actual}")


def main():
    print("=" * 78)
    print("A. 跨站点：pp 口径 vs log 口径")
    print("=" * 78)
    d = pd.read_csv(PROC / "raw_counts_sites.csv")
    d = d.drop_duplicates(["site", "quarter"], keep="last")
    w = d.pivot_table(index="site", columns="quarter", values="questions")

    so, ma = w.loc["stackoverflow"], w.loc["math"]
    b_so, b_ma = so["2022Q3"], ma["2022Q3"]

    rows = []
    for q in ["2022Q3", "2023Q1", "2023Q4", "2024Q4", "2025Q4", "2026Q3"]:
        tot = (so[q] - b_so) / b_so * 100
        ctrl = (ma[q] - b_ma) / b_ma * 100
        did_pp = tot - ctrl
        did_log = np.log(so[q] / b_so) - np.log(ma[q] / b_ma)
        share = did_pp / tot * 100 if abs(tot) > 1e-9 else np.nan
        rel_drop = (1 - np.exp(did_log)) * 100
        rows.append({"q": q, "so": int(so[q]), "math": int(ma[q]),
                     "so_pct": tot, "math_pct": ctrl, "did_pp": did_pp,
                     "share_pct": share, "did_log": did_log,
                     "rel_drop_pct": rel_drop})
        print(f"  {q}  SO={so[q]:>7,} ({tot:+7.2f}%)  math={ma[q]:>6,} ({ctrl:+7.2f}%)  "
              f"DiD_pp={did_pp:+7.2f}  份额={share:6.1f}%  |  "
              f"DiD_log={did_log:+.3f} 相对下降={rel_drop:6.1f}%")

    print()
    print("*** 关键矛盾检查 ***")
    r23 = [r for r in rows if r["q"] == "2023Q4"][0]
    r26 = [r for r in rows if r["q"] == "2026Q3"][0]
    print(f"  pp 口径 : DiD {r23['did_pp']:.1f}pp -> {r26['did_pp']:.1f}pp   "
          f"({'收敛' if abs(r26['did_pp']) < abs(r23['did_pp']) else '扩大'})")
    print(f"  log 口径: 相对下降 {r23['rel_drop_pct']:.1f}% -> {r26['rel_drop_pct']:.1f}%   "
          f"({'扩大' if r26['rel_drop_pct'] > r23['rel_drop_pct'] else '收敛'})")
    if abs(r26["did_pp"]) < abs(r23["did_pp"]) and r26["rel_drop_pct"] > r23["rel_drop_pct"]:
        # 检查文档是否已双口径并列处理（以报告是否包含 log 口径结果为准）
        report_txt = (ROOT / "outputs" / "report.md").read_text()
        dual = "91.2" in report_txt and "对数口径" in report_txt
        if dual:
            print("  已处理: 报告已双口径并列（pp 收敛 + log 扩大）并解释地板效应")
        else:
            WARN.append("pp 与 log 口径给出相反趋势：pp 收敛、log 扩大。"
                        "若报告只呈现 pp 口径并称『AI 效应是一次性水平冲击』，"
                        "会被反问『用比率看差距明明在扩大』。必须双口径并列并解释。")

    print()
    print("=" * 78)
    print("B. 报告 / 简历中出现的断言数字")
    print("=" * 78)
    check("SO 2022Q3->2023Q4 降幅 (%)", -55.6, r23["so_pct"], tol=0.15)
    check("Math 同期降幅 (%)", -3.9, r23["math_pct"], tol=0.15)
    check("2023Q4 DiD (pp)", -51.7, r23["did_pp"], tol=0.15)
    check("2023Q4 AI 归因份额 (%)", 93.0, r23["share_pct"], tol=0.3)
    check("2026Q3 SO 累计降幅 (%)", -99.0, r26["so_pct"], tol=0.15)
    check("2026Q3 Math 累计降幅 (%)", -89.0, r26["math_pct"], tol=0.15)
    check("2026Q3 DiD (pp)", -10.1, r26["did_pp"], tol=0.15)
    check("2026Q3 AI 归因份额 (%)", 10.2, r26["share_pct"], tol=0.3)
    check("2023Q1 AI 归因份额 (%)", 114.3,
          [r for r in rows if r["q"] == "2023Q1"][0]["share_pct"], tol=0.5)

    # 双期 log DiD（报告 3.1 中的 -0.773 / 下降 53.8%）
    did_log_23 = np.log(144895 / 326522) - np.log(19522 / 20308)
    check("双期 log DiD (β)", -0.773, did_log_23, tol=0.005, scale=1)
    check("对应相对下降 (%)", 53.8, (1 - np.exp(did_log_23)) * 100, tol=0.2)

    print()
    print("=" * 78)
    print("C. tag 面板：MATURE 组内是否真的无梯度")
    print("=" * 78)
    t = pd.read_csv(PROC / "raw_counts_tags.csv").drop_duplicates(
        ["unit", "quarter"], keep="last")
    tw = t.pivot_table(index="unit", columns="quarter", values="questions")
    mature = ["python", "javascript", "java", "c#", "php", "sql"]
    base = tw["2022Q3"]
    post = tw[["2022Q4", "2023Q1", "2023Q2", "2023Q3", "2023Q4"]].mean(axis=1)
    chg = ((post - base) / base * 100)
    sub = chg[mature]
    print(f"  MATURE 各领域降幅: {', '.join(f'{k}={v:.1f}%' for k, v in sub.items())}")
    print(f"  区间: {sub.min():.1f}% ~ {sub.max():.1f}%，极差 {sub.max()-sub.min():.1f}pp")
    check("MATURE 降幅下界（报告称 -30%）", -30.0, sub.max(), tol=6.0)
    check("MATURE 降幅上界（报告称 -45%）", -45.0, sub.min(), tol=8.0)

    print()
    print("=" * 78)
    print("D. 文档一致性：硬编码数字是否互相冲突")
    print("=" * 78)
    docs = {
        "report": ROOT / "outputs" / "report.md",
        "resume": ROOT / "resume" / "project_description.md",
        "readme": ROOT / "README.md",
        "deploy": ROOT / "DEPLOY.md",
    }
    pats = {
        "93%": r"93(\.0)?%",
        "10.2%": r"10\.2%",
        "-51.7": r"51\.7",
        "99%": r"99%",
    }
    for name, p in docs.items():
        if not p.exists():
            continue
        txt = p.read_text()
        hits = {k: len(re.findall(v, txt)) for k, v in pats.items()}
        print(f"  {name:8s} {hits}")

    # 检查是否出现了不该出现的夸大表述
    risky = {
        "AI 效应是一次性的水平冲击": "在 log 口径下不成立（差距持续扩大）",
        "AI 杀死 Stack Overflow": "过度简化",
        "因果证明": "观察性数据无法『证明』因果",
    }
    print()
    print("  过度声称扫描:")
    for name, p in docs.items():
        if not p.exists():
            continue
        txt = p.read_text()
        for k, why in risky.items():
            if k in txt:
                WARN.append(f"{name}: 出现表述「{k}」— {why}")
                print(f"    WARN {name}: 「{k}」")

    print()
    print("=" * 78)
    print(f"结果: {len(FAIL)} 项数字错误, {len(WARN)} 项需修正的表述")
    print("=" * 78)
    for f in FAIL:
        print("  FAIL:", f)
    for w in WARN:
        print("  WARN:", w)

    (ROOT / "outputs" / "audit.json").write_text(json.dumps(
        {"rows": rows, "mature_chg": sub.round(2).to_dict(),
         "fail": FAIL, "warn": WARN}, indent=2, default=float))
    return rows


if __name__ == "__main__":
    main()
