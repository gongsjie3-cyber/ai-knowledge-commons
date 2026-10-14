"""
数据可信度验证：区分「真实提问量崩塌」与「tag 分布/删除造成的技术假象」
======================================================================
背景:
  tag 面板显示 2025-2026 几乎所有 tag 趋近于 0，连新兴 tag 也不例外。
  在把它解释为「平台级衰亡」之前，必须先排除 API 侧的技术性解释：
    1. /questions 端点不返回已删除的帖子，若平台在后期大量删帖会低估计数
    2. tag 编辑/重打标签会改写历史问题的 tag 归属

验证逻辑:
  直接抓取 stackoverflow 站点的**全**。 0837575站提问数（不带 tagged 过滤）。
  若站点全量与 tag 面板的崩塌同步 -> 真实衰亡，非 tag 分布假象。
  同时抓 math 站点作为跨站对照：若 math 同期没有同等崩塌，
  则进一步支持「这是 stackoverflow 平台自身的衰亡」。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import (  # noqa: E402
    Collector, RAW, PROCESSED, SITE_BIRTH_TS, quarters,
)

CHECK_QUARTERS = ["2022Q3", "2023Q1", "2023Q4", "2024Q4", "2025Q4", "2026Q3"]


def main():
    c = Collector()
    c.prime_quota()
    print(f"quota_start={c.quota_remaining}")

    qmap = {lab: (s, e) for lab, s, e in quarters(2021, 1, 2026, 3)}
    rows = []
    for site in ["stackoverflow", "math"]:
        for lab in CHECK_QUARTERS:
            s, e = qmap[lab]
            n = c.count(site, None, s, e, lab)
            rows.append({"site": site, "quarter": lab, "sitewide_questions": n})
            print(f"  {site:<14} {lab}  sitewide={n}   (quota_rem={c.quota_remaining})")
            time.sleep(0.2)

    out = PROCESSED / "sitewide_check.csv"
    rows_df = None
    import csv
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["site", "quarter", "sitewide_questions"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n[write] {out}")
    return rows


if __name__ == "__main__":
    main()
