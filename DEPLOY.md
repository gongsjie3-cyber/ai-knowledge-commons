# 发布与申请清单

> 目标：让这个项目在简历上变成一个**可点击、可验证、可炫耀**的资产，而不是一行自我陈述的文字。
> 全程免费，预计 20 分钟。

## 当前状态

| 项目 | 地址 |
|---|---|
| GitHub 仓库 | https://github.com/gongsjie3-cyber/ai-knowledge-commons |
| 在线看板 | https://gongsjie3-cyber.github.io/ai-knowledge-commons/ |

仓库已推送（489 个文件，2 个 commit，public）。看板需在仓库 Settings → Pages 中启用（Source 选 `main` / `/docs`）后生效。

**简历格式**：
```
生成式 AI 与知识公共品的供给塌陷 — 基于 Stack Exchange 网络的准自然实验
github.com/gongsjie3-cyber/ai-knowledge-commons · 在线看板: gongsjie3-cyber.github.io/ai-knowledge-commons
```

## 一、需要「申请」的：只有 2 项

### 1. Stack Exchange API key（强烈建议，1 分钟）
无 key 配额 300 请求/天，有 key **3000/天**——这是本项目扩展（全站点面板、回答端数据）的唯一硬约束。

1. 打开 https://stackapps.com/apps/oauth/register
2. Application Name 填任意（如 `knowledge-commons-research`）
3. OAuth Domain 填 `localhost`，其他留空
4. 提交后得到一个 **Key**（一串字母数字）
5. 在项目根目录建 `.env`，写入一行：

```
SE_API_KEY=你的key
```

> `.env` 已在 `.gitignore` 中，**不会被提交**。绝不要把 key 硬编码进任何 .py 文件。

有了 key 之后，跨站点全面板可以一次跑完：
```bash
python src/collect.py --plan all
```

### 2. GitHub 账号（若已有则跳过）
简历上的项目链接几乎都指向 GitHub。没有就注册一个，用户名建议用**拼音/真名**（`zhangsan` 好过 `coolcoder99`），因为 HR 会直接读用户名。

**其他都不用申请。** 专利不适用（这是数据分析项目）；投论文周期 6–18 个月且当前样本量不够，正确做法是先给导师看、转成课程论文或 working paper。

---

## 二、上传到哪里：按优先级做前两项就够

| # | 平台 | 作用 | 是否必做 |
|---|---|---|---|
| 1 | **GitHub 仓库** | 简历主链接，证明代码与工程规范 | ✅ 必做 |
| 2 | **GitHub Pages** | **在线演示链接**——HR 会点，且点了就有东西看 | ✅ 强烈建议 |
| 3 | Zenodo | 给仓库打 DOI，学术引用用 | 走申博时建议 |
| 4 | Gitee 镜像 | 国内访问友好 | 可选 |

### 为什么第 2 项最值钱
HR 和面试官**不会 clone 你的仓库**，但会点链接。一个打开就能交互的看板，和一行「参与了某数据分析项目」之间，是数量级的差距。

---

## 三、具体命令（可直接复制）

```bash
cd ai-knowledge-commons

# 1. 生成 Pages 用的 docs/ 目录
make docs

# 2. 初始化并首次提交
git init
git add .
git commit -m "Initial commit: GenAI x knowledge commons causal study"

# 3. 在 GitHub 网页上创建一个空仓库（不要勾选 README / .gitignore / license）
#    然后替换下面的地址：
git remote add origin https://github.com/你的用户名/ai-knowledge-commons.git
git branch -M main
git push -u origin main
```

推送若提示输入密码：GitHub 已不支持账号密码，需到
**Settings → Developer settings → Personal access tokens** 生成一个 token（勾选 `repo`），用 token 当密码。

### 开启 GitHub Pages
推送后打开仓库 → **Settings → Pages** → Source 选 `Deploy from a branch` → Branch 选 `main`、目录选 `/docs` → Save。
约 1 分钟后生效，地址形如：

```
https://你的用户名.github.io/ai-knowledge-commons/
```

**这就是简历上要放的那个链接。**

---

## 三·五 · 仓库元数据（Description / topics / Website）

改这三个字段必须走网页（SSH 无此权限）。路径：仓库主页右上角 **⚙️ 齿轮图标**（Edit repository metadata；旧版在 Settings → General → About）。

直接复制以下内容：

**Description**（≤350 字符，推荐英文，国际通用）：
```
Generative AI and the knowledge commons: a quasi-natural experiment quantifying ChatGPT's substitution of community-produced expertise on Stack Exchange — DiD, Poisson PPML, wild cluster bootstrap, fully reproducible.
```

中文备选：
```
生成式AI与知识公共品：基于Stack Exchange网络的准自然实验，量化ChatGPT对人类知识生产的替代效应
```

**Topics**（每行一个，回车确认，建议 10 个）：
```
causal-inference
difference-in-differences
panel-data
econometrics
quasi-experiment
generative-ai
data-science
python
stack-exchange
information-systems
```

**Website**（容易被忽略但很值）：
```
https://gongsjie3-cyber.github.io/ai-knowledge-commons/
```
填上后，仓库主页 About 区域会出现一个可直接点击的链接——HR 不用去 Settings 找 Pages 就能进看板。

## 四、简历上怎么放

推荐格式（一行搞定，链接可点）：

```
生成式 AI 与知识公共品的供给塌陷 — 基于 Stack Exchange 网络的准自然实验
github.com/xxx/ai-knowledge-commons · 在线看板: xxx.github.io/ai-knowledge-commons
```

要点：
- **链接放项目名下面，不要藏在段落里**
- 如果简历系统只支持纯文本，也要把 URL 完整写出（很多人会手敲）
- 国内投递担心访问问题，可再附一个 Gitee 镜像链接
- 仓库 README 是别人点进来看到的第一屏，务必保持整洁（本项目 README 已按此标准写好）

---

## 五、不值得做的事

- ❌ 买域名——`xxx.github.io` 完全够用，自定义域名反而显得用力过猛
- ❌ 急着投期刊——先把样本扩到全站点 + 回答端数据，再谈投稿
- ❌ 把 `data/raw/` 删掉以「精简仓库」——那些原始 API 响应是复现性的凭据，正是它让这个项目区别于调包练习
