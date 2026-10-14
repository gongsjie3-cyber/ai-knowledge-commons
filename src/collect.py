"""
Stack Exchange 面板数据采集：配额感知 + 断点续传
=================================================
数据源: Stack Exchange REST API v2.3  (/questions 端点)
计数方式: 对每个 (site, tag, 时间窗) 组合请求一次，读取响应中的 `total` 字段。
         使用 filter=%21nNPvSNVZJS，该 filter 的 schema 显式包含 `.total`。

配额约束:
  - 无 API key: 300 请求 / 天 / IP
  - 有 API key: 3000 请求 / 天 (免费注册: https://stackapps.com/apps/oauth/register)
  脚本会在配额触及安全下限时主动停机并报告已完成进度，
  剩余任务可在次日或配置 key 后原样续跑（缓存命中即跳过，不重复消耗配额）。

用法:
    python src/collect.py --plan tags          # 采集 SO 站内 tag 面板
    python src/collect.py --plan sites         # 采集跨站点面板
    python src/collect.py --plan tags --budget 50
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.stackexchange.com/2.3/questions"
# 该 filter 的 included_fields 显式包含 'total'，已实测验证：
# items / has_more / quota_max / quota_remaining / total
COUNT_FILTER = "!nNPvSNVZJS"

# 无 key 时保留的安全余量，触底即停机（避免把配额彻底打空）
SAFETY_FLOOR = int(os.environ.get("SE_SAFETY_FLOOR", "8"))
SLEEP_BETWEEN = 0.18

API_KEY = os.environ.get("SE_API_KEY", "").strip()


# --------------------------------------------------------------------------
# 面板设计
# --------------------------------------------------------------------------
# 冲击时点: 2022-11-30 ChatGPT 发布。按季度切分时 2022Q4 为混合期（partial-treated），
# 分析中作为处理起始期并在稳健性章节单独说明。

def quarters(start_year: int, start_q: int, end_year: int, end_q: int):
    """生成季度区间列表 [(label, start_ts, end_ts), ...]，左闭右开。"""
    out = []
    y, q = start_year, start_q
    while (y, q) <= (end_year, end_q):
        m_start = 3 * (q - 1) + 1
        y_end, m_end = (y, m_start + 3) if q < 4 else (y + 1, 1)
        s = datetime(y, m_start, 1, tzinfo=timezone.utc)
        e = datetime(y_end, m_end, 1, tzinfo=timezone.utc)
        out.append((f"{y}Q{q}", int(s.timestamp()), int(e.timestamp())))
        q = 4 if False else (q + 1 if q < 4 else 1)
        if q == 1:
            y += 1
    return out


QUARTERS = quarters(2021, 1, 2026, 3)

# ---- SO 站内 tag 面板：主识别样本 -------------------------------------------
# 按「LLM 训练语料覆盖度」的先验分成三组，组标签在数据观测前即固定，事后不做重分类。
# 预算核算: 11 tags x 23 季度 = 253 请求 + 11 次累计存量请求 = 264，
#           落在无 key 配额 300/天之内；剩余预算留给 SITES 计划。
TAGS = [
    # MATURE: 2022 年前已积累海量公开问答 -> LLM 语料覆盖最充分 -> 预期受冲击最重
    ("python", "MATURE"),
    ("javascript", "MATURE"),
    ("java", "MATURE"),
    ("c#", "MATURE"),
    ("php", "MATURE"),
    ("sql", "MATURE"),
    # EMERGING: 2022 年后才兴起的新技术栈 -> LLM 语料近乎空白 -> 天然安慰剂组
    ("bun", "EMERGING"),
    ("sveltekit", "EMERGING"),
    ("htmx", "EMERGING"),
    # NATIVE_AI: AI 原生 tag，用于检验是否存在话题迁移而非单纯衰减
    ("langchain", "NATIVE_AI"),
    ("openai-api", "NATIVE_AI"),
]

# 处理强度基准：各 tag 截至 ChatGPT 发布前的历史累计提问数。
# 该值代理「该知识领域进入 LLM 训练语料的充分程度」，是 H1 的连续处理变量。
CHATGPT_RELEASE = "2022-11-30"
CUMULATIVE_CUTOFF_TS = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp())
SITE_BIRTH_TS = int(datetime(2008, 7, 31, tzinfo=timezone.utc).timestamp())

# ---- 跨站点面板：辅助识别 / 稳健性 -----------------------------------------
SITES = [
    ("stackoverflow", "TREATED"),   # 软件开发问答，LLM 直接替代性最强
    ("math", "CONTROL"),            # 数学，需要符号推导与严格证明
    ("superuser", "CONTROL"),       # 通用软件使用
    ("serverfault", "CONTROL"),     # 系统运维，强依赖环境上下文
    ("askubuntu", "CONTROL"),       # Linux 桌面发行版配置
    ("english", "CONTROL"),         # 英语语言与用法
    ("stats", "CONTROL"),           # 统计学
    ("salesforce", "CONTROL"),      # 企业级 SaaS 配置
]


# --------------------------------------------------------------------------
# 请求层
# --------------------------------------------------------------------------
class QuotaExhausted(RuntimeError):
    pass


class Collector:
    def __init__(self, budget: int | None = None, dry_run: bool = False):
        self.session = requests.Session()
        self.budget = budget
        self.spent = 0
        self.dry_run = dry_run
        self.quota_remaining: int | None = None
        self.hits = 0

    def cache_path(self, site: str, tag: str, label: str) -> Path:
        slug = urllib.parse.quote_plus(tag)
        return RAW / f"{site}__{slug}__{label}.json"

    def _get(self, params: dict) -> dict:
        for attempt in range(3):
            r = self.session.get(
                API_BASE, params=params, timeout=30,
                headers={"Accept-Encoding": "gzip, deflate"},
            )
            if r.status_code == 400:
                raise RuntimeError(f"bad request: {r.text[:200]}")
            if r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            return r.json()
        raise RuntimeError("retries exhausted")

    def count(self, site: str, tag: str | None, start_ts: int, end_ts: int, label: str) -> int | None:
        """返回该 (site, tag, 窗口) 内的提问数。命中缓存则不计配额。"""
        key_slug = tag or "__ALL__"
        cache = self.cache_path(site, key_slug, label)
        if cache.exists():
            self.hits += 1
            try:
                return json.loads(cache.read_text()).get("total")
            except json.JSONDecodeError:
                cache.unlink()

        if self.dry_run:
            return None
        if self.budget is not None and self.spent >= self.budget:
            raise QuotaExhausted(f"budget {self.budget} reached")
        if self.quota_remaining is not None and self.quota_remaining <= SAFETY_FLOOR:
            raise QuotaExhausted(f"quota floor reached (rem={self.quota_remaining})")

        params = {
            "site": site,
            "fromdate": start_ts,
            "todate": end_ts,
            "pagesize": 1,
            "filter": COUNT_FILTER,
        }
        if tag:
            params["tagged"] = tag
        if API_KEY:
            params["key"] = API_KEY

        payload = self._get(params)
        self.spent += 1
        self.quota_remaining = payload.get("quota_remaining")

        backoff = payload.get("backoff")
        total = payload.get("total")
        if total is None:
            raise RuntimeError(f"no 'total' in response: {str(payload)[:200]}")

        cache.write_text(json.dumps({
            "site": site, "tag": key_slug, "label": label,
            "start_ts": start_ts, "end_ts": end_ts,
            "total": total,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }))

        time.sleep(SLEEP_BETWEEN + (backoff or 0))
        return total

    def prime_quota(self):
        """先打一次最便宜的请求，读出当前配额余量。"""
        p = {"site": "stackoverflow", "pagesize": 1, "tagged": "python",
             "fromdate": QUARTERS[0][1], "todate": QUARTERS[0][2], "filter": COUNT_FILTER}
        if API_KEY:
            p["key"] = API_KEY
        try:
            self.quota_remaining = self._get(p).get("quota_remaining")
        except Exception as exc:  # 配额已空或网络异常，交由主循环处理
            print(f"[warn] prime failed: {exc}")


def run(plan: str, budget: int | None, dry_run: bool):
    c = Collector(budget=budget, dry_run=dry_run)
    if not dry_run:
        c.prime_quota()
    print(f"[plan={plan}] quarters={len(QUARTERS)} key={'yes' if API_KEY else 'no'} "
          f"quota_start={c.quota_remaining} budget={budget or 'unlimited'}")

    intensity = {}
    rows = []
    try:
        if plan in ("tags", "all"):
            # --- 第一步：抓处理强度基准（累计存量），每个 tag 仅 1 次请求 ---
            for tag, group in TAGS:
                cum = c.count("stackoverflow", tag, SITE_BIRTH_TS, CUMULATIVE_CUTOFF_TS, "cum_2022")
                intensity[tag] = cum
                print(f"  intensity/{tag:<12} cumulative_to_2022={cum}")
            cum_out = PROCESSED / "tag_intensity.json"
            cum_out.write_text(json.dumps(intensity, indent=2))
            print(f"[write] {cum_out}")

            # --- 第二步：抓季度面板 ---
            for tag, group in TAGS:
                for label, s, e in QUARTERS:
                    n = c.count("stackoverflow", tag, s, e, label)
                    rows.append({"unit_type": "tag", "unit": tag, "group": group,
                                 "site": "stackoverflow", "quarter": label, "questions": n})
                print(f"  tag/{tag:<12} done (spent={c.spent}, quota_rem={c.quota_remaining})")

        if plan in ("sites", "all"):
            for site, role in SITES:
                for label, s, e in QUARTERS:
                    n = c.count(site, None, s, e, label)
                    rows.append({"unit_type": "site", "unit": site, "group": role,
                                 "site": site, "quarter": label, "questions": n})
                print(f"  site/{site:<12} done (spent={c.spent}, quota_rem={c.quota_remaining})")

        status = "COMPLETE"
    except QuotaExhausted as exc:
        status = f"PARTIAL: {exc}"
        print(f"\n[halt] {exc}")

    import csv
    if rows:
        # 固定文件名、每次覆盖：重跑不会堆积重复分片，
        # 结果始终与 data/raw 中的原始响应一一对应。
        out = PROCESSED / f"raw_counts_{plan}.csv"
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"[write] {out}  rows={len(rows)}")

    print(f"\n=== spend={c.spent}  cached_hits={c.hits}  quota_rem={c.quota_remaining}  {status} ===")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=["tags", "sites", "all"], default="tags")
    ap.add_argument("--budget", type=int, default=None, help="本次最大请求数")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.plan, a.budget, a.dry_run)
