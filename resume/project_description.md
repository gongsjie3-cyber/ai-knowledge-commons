# 项目简历描述（直接可用）

## 英文版

**Generative AI and the Knowledge Commons: A Quasi-Natural Experiment on Stack Exchange**
*Independent research project · Python (pandas / statsmodels / matplotlib) · REST API data engineering · 2026.08*

Designed and executed an end-to-end causal study of how ChatGPT's release reshaped voluntary knowledge production in online communities. Built a quota-aware, resumable data pipeline over the Stack Exchange API (253 tag-quarter observations plus a balanced 8-site x 23-quarter site-level panel, 184 observations), then estimated two-way fixed-effects DiD with unit-specific quadratic trends, Poisson PPML, and Rademacher wild cluster bootstrap.

- **Quantified attribution, not just trends**: decomposed Stack Overflow's −99% collapse into an LLM-attributable component and a platform-wide decline, using Mathematics (a formal-proof domain LLMs cannot substitute) as a clean control — LLM substitution explains **93% of the year-one drop (percentage-point terms)**, while the ratio gap vs. the control **keeps widening (53.8% → 91.2% by 2026)**: the apparent convergence is a floor effect, and the late-stage collapse is driven by a platform-wide decline rather than fading AI impact.
- **Rejected my own prior hypothesis with data**: the expected dose-response gradient (domains with denser training corpora get substituted more) vanished once technology-adoption trends were absorbed (β≈0, p=0.22–0.92 across specs); evidence instead supports a **threshold model** of substitution — a finding with direct implications for the "model collapse" debate.
- **Survived a failed identification honestly**: caught a pre-trend violation through a placebo-in-time test (initial p=1e-18), diagnosed it as confounded technology-adoption curves, fixed it with unit-specific trends, and re-passed all placebo tests — documented the full path in the write-up rather than reporting only the final spec.
- **Delivered a fully reproducible research artifact**: one-command pipeline (`collect → verify → analyze → figures`), versioned raw-data cache, and a 5-figure analytical report with an interactive dashboard.

## 中文版

**生成式 AI 与知识公共品：基于 Stack Exchange 网络的准自然实验**
*独立研究项目 · Python（pandas / statsmodels / matplotlib）· REST API 数据工程 · 2026.08*

独立完成从研究设计到结论的完整因果研究：ChatGPT 发布如何重塑在线社区的人类知识生产。基于 Stack Exchange API 构建配额感知、可断点续传的数据管线（站内 11 个知识领域 × 23 个季度共 253 个面板观测，以及跨 8 个站点 × 23 个季度共 184 个站点级面板观测），使用双向固定效应 DiD（含领域特定二次趋势）、Poisson PPML 与 Rademacher wild cluster bootstrap 进行估计。

- **量化归因而非仅描述趋势**：以数学站点（LLM 无法替代的形式证明领域）为干净对照，把 Stack Overflow 累计 −99% 的降幅分解为 LLM 直接替代部分与平台级衰亡部分——发现 LLM 直接替代在发布后一年内解释 **93%** 的降幅（百分点口径）；而对数口径下相对差距从 53.8% **持续扩大到 91.2%**，份额的收敛只是跌至地板后的算术结果——后期崩塌的主体是跨领域衰亡，但 AI 的相对影响并未消退；
- **用数据否定自己的先验假设**：预期中的「语料越充分、替代越强」剂量-反应关系在吸收技术采用趋势后消失（各规格 β≈0，p=0.22–0.92），证据支持**门槛效应**而非连续梯度——对「模型自噬」争论有直接含义；
- **诚实处理识别失败**：通过伪处理时间检验捕获预趋势违反（初检 p=1e-18），诊断出新技术栈采用曲线这一混淆源，引入领域特定趋势修复后全部安慰剂检验通过，并在报告中完整记录这一过程而非只呈现最终规格；
- **交付完全可复现的研究工件**：一条命令跑通采集→验证→分析→成图，含原始数据缓存版本管理与交互式看板。

---

## 面试口径（怎么讲这个故事）

**30 秒版本**：
"我做了一个因果推断项目，研究 ChatGPT 到底抢走了多少 Stack Overflow 的提问。关键不是画出下降曲线——谁都画得出——而是把 −99% 拆开：我用数学站点做对照，因为它需要形式证明、LLM 替代不了。结果发现 LLM 直接替代解释了头一年降幅的 93%（按百分点算），但这里有个容易踩的坑：按比率看，SO 相对数学站的差距一直在扩大（53.8%→91.2%），百分点口径的收敛只是 SO 已经跌到地板的算术结果。所以准确的说法是：头一年的暴跌主要是 LLM 直接替代，后面的崩塌主体是连数学站也一起跌的全网性衰亡，但 AI 的相对影响并没有消退。另外我原来的假设『训练语料越多的领域被替代得越狠』被数据否定了——实际是门槛效应，过线就全被替代，跟语料多少没关系。"

**如果被问"这有什么难点"**：
"两个。一是平行趋势被新技术栈的采用曲线污染，我第一次跑安慰剂检验 p 值是 10 的负 18 次方，当场发现问题；修复方式是给每个领域放独立的二次趋势，之后安慰剂全部通过。二是 cluster 只有 11 个，渐近聚类标准误不可靠，我改用 Rademacher wild cluster bootstrap 重做了推断。"

**如果被问"如果继续做"**：
"三条路：把 8 个对照站点跑全做正式的面板 DiD；补 Stack Overflow 的回答端数据，区分需求塌陷和供给塌陷——后者才是 model collapse 的真正来源；把分析扩到中文技术社区（如掘金/CSDN），检验门槛效应是否跨语言成立。"
