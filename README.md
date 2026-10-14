# Generative AI and the Knowledge Commons

**ChatGPT 的发布是否、以及在多大程度上替代了在线社区中人类自愿的知识生产？**
一个基于 Stack Exchange 网络的准自然实验。数据全部实时采集自官方 API，全流程一条命令复现。

## 核心发现

1. **归因分解**：以数学站点（形式证明领域，LLM 无法替代）为对照，Stack Overflow 在 2022Q3→2023Q4 的降幅中 **93% 可由生成式 AI 解释（DiD = −51.7pp）**；但到 2026Q3，AI 份额萎缩到 **10.2%**——「AI 吸干 Stack Overflow」的流行叙事把 AI 的作用高估了近 10 倍，其余是跨越整个 Stack Exchange 网络的平台级衰亡。
2. **门槛效应而非剂量-反应**：先验假设「训练语料越充分的领域被替代越狠」被数据否定。加入领域特定二次趋势后，连续处理强度的系数从不显著变为不显著（β≈0, p=0.22–0.92），成熟领域组内斜率 +4.8pp/log（p=0.43）。替代由「LLM 能力是否跨过该领域的门槛」决定，与语料密度无关。
3. **方法诚实性**：初版规格的伪处理时间安慰剂未通过（p=1e-18），诊断出新技术栈采用曲线造成的预趋势污染，引入领域特定趋势后全部安慰剂通过。完整过程记录在报告中。

## 仓库结构

```
├── src/
│   ├── collect.py          # 配额感知 + 断点续传的采集器（支持 SE_API_KEY）
│   ├── verify_sitewide.py  # 排除删帖/重打标签技术假象的验证
│   ├── analyze.py          # TWFE / PPML / wild bootstrap / 安慰剂 / Honest DiD
│   └── figures.py          # 全部图表
├── data/
│   ├── raw/                # API 原始响应缓存（重跑不消耗配额）
│   └── processed/          # 面板 CSV + 处理强度 JSON
├── outputs/
│   ├── report.md           # 完整分析报告
│   ├── figures/            # fig1–fig5
│   ├── dashboard/index.html
│   └── results.json
```

## 复现

```bash
pip install -r requirements.txt

# 1. 采集（有缓存即跳过，不消耗配额；无 key 每天 300 请求）
python src/collect.py --plan tags     # SO 站内 tag 面板（已缓存）
python src/collect.py --plan sites    # 跨站点面板（需次日配额或注册 key）

# 2. 验证 + 分析 + 成图
python src/verify_sitewide.py
python src/analyze.py
python src/figures.py
```

配额说明：无 key 300 请求/天/IP；在 https://stackapps.com/apps/oauth/register 免费注册后设 `SE_API_KEY`，提升至 3000/天，`--plan all` 一次跑完。

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
| openai-api | 42 |
| htmx | 73 |
| langchain | 1 |
| bun | **0**（ChatGPT 发布时该技术栈尚未存在） |
