# Generative AI and the Knowledge Commons

**ChatGPT 的发布是否、以及在多大程度上替代了在线社区中人类自愿的知识生产？**
一个基于 Stack Exchange 网络的准自然实验。数据全部实时采集自官方 API，全流程一条命令复现。

## 核心发现

1. **归因分解（双口径）**：以数学站点（形式证明领域，LLM 难以替代）为对照，LLM 直接替代解释了 Stack Overflow 2022Q3→2023Q4 降幅的 **93%**（DiD = −51.7pp，百分点口径）；但对数口径下相对差距同期从 53.8% **持续扩大到 91.2%**——后期降幅的主体是跨越整个 Stack Exchange 网络的平台级衰亡，而份额的收敛只是 SO 跌至地板后的算术结果，并非 AI 影响消退。
2. **门槛效应而非剂量-反应**：先验假设「训练语料越充分的领域被替代越狠」被数据否定。加入领域特定二次趋势后，连续处理强度的系数从不显著变为不显著（β≈0, p=0.22–0.92），成熟领域组内斜率 +0.4pp/log（p=0.955）。替代由「LLM 能力是否跨过该领域的门槛」决定，与语料密度无关。
3. **方法诚实性**：初版规格的伪处理时间安慰剂未通过（p=1e-18），诊断出新技术栈采用曲线造成的预趋势污染，引入领域特定趋势后全部安慰剂通过。完整过程记录在报告中。

## 仓库结构

```
├── src/
│   ├── collect.py          # 配额感知 + 断点续传的采集器（支持 SE_API_KEY）
│   ├── verify_sitewide.py  # 排除删帖/重打标签技术假象的验证
│   ├── analyze.py          # tag 面板：TWFE / PPML / wild bootstrap / 安慰剂 / Honest DiD
│   ├── analyze_sites.py    # 跨站点面板：以 Mathematics 为 numeraire 的相对对数差分 DiD
│   ├── figures.py          # tag 面板图表（fig1–fig5）
│   ├── figures_sites.py    # 跨站点图表（fig6–fig8）
│   └── audit.py            # 发布前数字审计：用原始数据重算每条公开断言
├── data/
│   ├── raw/                # API 原始响应缓存（重跑不消耗配额）
│   └── processed/          # 面板 CSV + 处理强度 JSON
├── outputs/
│   ├── report.md           # 完整分析报告
│   ├── figures/            # fig1–fig8（9 张）
│   ├── dashboard/index.html
│   ├── results.json        # tag 面板估计结果
│   └── results_sites.json   # 跨站点面板估计结果
└── resume/
    ├── project_description.md   # 简历项目描述（中英）
    ├── resume_placement.md      # 放置位置与分岗位包装
    └── plan.md                  # 四周实施方案与避坑清单
```

## 复现

```bash
pip install -r requirements.txt

make all        # 一步跑完：采集 → 验证 → 站内分析 → 跨站分析 → 成图
```

或分步执行：

```bash
# 1. 采集（命中缓存即跳过，不重复消耗配额）
python src/collect.py --plan tags       # 站内 tag 面板（已缓存）
python src/collect.py --plan sites      # 跨站点面板（已缓存）

# 2. 验证 + 分析 + 成图
python src/verify_sitewide.py           # 排除删帖/重打标签的技术假象
python src/analyze.py                   # 站内 tag 面板
python src/analyze_sites.py             # 跨站点面板
python src/figures.py                   # fig1–fig5
python src/figures_sites.py             # fig6–fig8

# 3. 发布前数字审计（可选）
python src/audit.py                     # 用原始数据重算每条公开断言
```

配额说明：无 key 300 请求/天/IP；在 https://stackapps.com/apps/oauth/register 免费注册后设 `SE_API_KEY`（写入 `.env`），提升至 3000/天，`--plan all` 一次跑完。`data/raw/` 中缓存了全部 API 原始响应，重跑不消耗配额。

## 数据与处理强度

| 领域 | 截至 2022-01 的累计提问数（= LLM 语料覆盖度代理） |
|---|---|
| javascript | 2,263,914 |
| python | 1,802,367 |
| java | 1,782,740 |
| c# | 1,492,939 |
| php | 1,395,083 |
| sql | 607,492 |
| sveltekit | 308 |
| htmx | 73 |
| openai-api | 42 |
| langchain | 1 |
| bun | **0**（ChatGPT 发布时该技术栈尚未存在） |
