<p align="center">
  <h1 align="center">📈 mystock</h1>
  <p align="center"><strong>AI 多智能体驱动的每日股市深度研究系统</strong></p>
  <p align="center">三层递进 · 多空博弈推演 · 不只是信息聚合</p>
</p>

---

## 🧠 核心理念

> **每条新闻不只说「发生了 X」，还要追问「然后呢？」**

这个系统不是新闻摘要器，而是一个**多空博弈推演引擎**。每个分析维度必须回答三个问题：

| 视角 | 问题 |
|------|------|
| 🟢 **多方** | Bull case — 为什么看涨？证据是什么？ |
| 🔴 **空方** | Bear case — 为什么看跌？证据是什么？ |
| 🧑 **你** | 综合判断 — 概率化结论，不骑墙 |

每条信息都经过四层追问：
- 对谁有利？对谁有害？
- 和看似无关的事件有无隐性关联？
- 历史上类似情况后市场怎么走？
- **聪明钱在这个背景下最可能做什么？**

---

## 🏗️ 引擎架构（v2.0）

```
scripts/run_deep_research.py          ← 主入口
│
├─ 🔍 第一层：信息采集（并行 5 agent）
│  ├─ 板块深度搜索      → 半导体 + AI 产业链
│  ├─ 个股深度搜索      → 所有关注标的
│  ├─ 宏观 + 资金流向   → 美联储/央行/北向南向资金
│  ├─ 大V推文抓取       → Grok + X API v2
│  └─ 加密货币专项      → BTC/ETH 链上 + 情绪
│
├─ ⚔️ 第二层：深度推演（并行 3 agent）
│  ├─ 多空博弈台         → 每市场 Bull vs Bear 对撞
│  ├─ 线索串联 + 历史镜鉴 → 隐性关联 + 聪明钱推理
│  └─ 催化剂场景推演     → 前瞻双场景沙盘
│
└─ 📝 第三层：报告撰写（串行）
   ├─ 主笔整合 → 暗色主题 HTML 专业研报
   └─ QQ 邮件发送
```

---

## 🌍 覆盖市场

| 市场 | 范围 |
|------|------|
| 🇺🇸 **美股** | 纳斯达克、纽交所、S&P 500 |
| 🇨🇳 **A股** | 沪深两市 |
| 🇭🇰 **港股** | 香港交易所 |
| 🪙 **加密货币** | BTC、ETH |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/radium1234/mystock.git
cd mystock
```

### 2. 配置 API 凭证

```bash
cp .env.example .env
cp config.example.json config.json
```

编辑 `.env` 填入你的 API 密钥：
- **OpenRouter** — DeepSeek Chat 直连（[注册](https://openrouter.ai/)）
- **xAI** — Grok 用于推特搜索（[注册](https://x.ai/api)）
- **Twitter API v2** — 推文抓取（[注册](https://developer.x.com/)）
- **HTTP 代理** — 国内访问 xAI 需要 Clash Verge 代理

编辑 `config.json` 填入：
- QQ 邮箱 + SMTP 授权码（[获取授权码](https://service.mail.qq.com/)）

### 3. 安装依赖

```bash
pip install requests python-dotenv
```

### 4. 编辑需求单

编辑 `requirements.md`，勾选你想研究的标的和维度。

### 5. 运行

```bash
# 完整深度研究
python scripts/run_deep_research.py

# 跳过邮件
python scripts/run_deep_research.py --no-email

# 跳过推特（X API 配额用完时）
python scripts/run_deep_research.py --no-twitter

# 保存中间 JSON 数据便于调试
python scripts/run_deep_research.py --save-json
```

---

## 🔧 单次 API 调用

```bash
# DeepSeek 通用问答
python scripts/grok_api.py "分析今天NVDA的走势"

# Grok + X API 搜推特
python scripts/grok_api.py --xai --search "搜 @aleabitoreddit 的推文"

# xAI Grok 直调
python scripts/grok_api.py --xai "直接问 Grok"

# 查看可用模型
python scripts/grok_api.py --list-models
```

---

## 📬 发送邮件

```bash
# 发送 HTML 内容
python scripts/send_email.py --subject "今日研报" --body "<h1>内容</h1>"

# 发送报告文件
python scripts/send_email.py --subject "今日研报" --file "output/report.html"
```

---

## ⏰ 定时任务

通过 Windows 任务计划程序自动运行：

```powershell
# 创建计划任务（每天 09:00 和 21:00）
powershell -File scripts/create_schtask.ps1
```

- 任务名：`mystock-daily-research`
- 时区：`Asia/Shanghai`
- 入口：`scripts/run_daily.ps1`

---

## 📂 项目结构

```
mystock/
├── requirements.md              # 📋 研究需求单 + 思考框架（编辑这个！）
├── config.example.json          # 📧 邮件配置模板
├── .env.example                 # 🔑 环境变量模板
│
├── scripts/
│   ├── run_deep_research.py     # ⚙️ 深度研究主引擎（三层递进）
│   ├── grok_api.py              # 🔌 统一 API 助手（DeepSeek/Grok/X）
│   ├── send_email.py            # 📬 QQ 邮件发送
│   ├── run_daily.ps1            # 🪟 计划任务入口
│   └── create_schtask.ps1       # 🔧 创建 Windows 计划任务
│
├── prompts/deep-research/       # 🎭 提示词库（14个角色 prompt）
│   ├── system-base.md           # 通用深度思考约束
│   ├── sector-deep.md           # 板块深度搜索
│   ├── stock-deep.md            # 个股深度搜索
│   ├── macro-fundflow.md        # 宏观 + 资金面
│   ├── crypto-deep.md           # 加密货币专项
│   ├── bull-bear-arena.md       # 多空博弈台
│   ├── dot-connecting.md        # 线索串联
│   ├── catalyst-scenario.md     # 催化剂场景推演
│   └── ...                      # 更多专项 prompt
│
├── templates/
│   └── deep-report.html         # 🎨 暗色主题专业研报模板
│
├── memory/
│   └── thinking-patterns/       # 🧠 用户思考习惯记忆（自动注入 prompt）
│
└── output/                      # 📄 生成的研报（gitignore）
    └── YYYY-MM-DD-深度研报.html
```

---

## 🛡️ 安全说明

**API 密钥和邮箱密码绝不会上传到 GitHub。** 仓库只包含 `.example` 模板文件：

| 文件 | 状态 |
|------|------|
| `.env` | 🔒 `.gitignore` 排除 |
| `config.json` | 🔒 `.gitignore` 排除 |
| `.env.example` | ✅ 安全模板 |
| `config.example.json` | ✅ 安全模板 |

---

## 🔬 研报内容亮点

每份研报包含：

- ⚔️ **多空博弈台** — 双列 Bull vs Bear 对比，附证据
- 🔗 **线索串联** — 看似无关事件的隐性关联
- 🪞 **历史镜鉴** — 「现在最像历史上的哪段行情？」
- 🧠 **聪明钱推理** — 机构在这个背景下最可能做什么
- 🎯 **催化剂场景推演** — 上行情景 vs 下行情景
- 📊 **标的深度分析** — 每标的含 mini bull/bear
- 📡 **大V信号解读** — 含反向阅读（极端情绪 = 反向指标）
- ⚠️ **风险矩阵** — 概率 × 影响程度
- 🧭 **操作启示** — 涨 / 跌 / 横盘三场景应对

---

## 📋 API 路由

| 用途 | 模型 | 方式 | 价格 |
|------|------|------|------|
| 通用分析/预测/报告 | DeepSeek Chat | OpenRouter 直连 | ~$0.14/M 输入 |
| 推特/X 数据搜索 | Grok 4.3 | xAI API（需代理） | ~$0.00125/M |
| X 推文实际抓取 | 无（直接调用） | X API v2 | 免费配额 |
| 邮件发送 | 无（直接调用） | QQ SMTP | 免费 |

---

## 🧠 思考框架

系统内置用户的投资分析框架，每次运行自动注入 agent prompt：

- **大资金行为逻辑** — IPO 掩护出货、大宗交易异动
- **多空博弈思维** — 每个判断必须 Bull + Bear 双面呈现
- **大V信号反向阅读** — 极端一致预期往往是反向信号
- **历史镜鉴** — 寻找历史上最相似的行情片段
- **跨市场联动** — 美股→A股/港股传导、加密-纳斯达克相关性
- **资金面 ≠ 基本面** — 区分短期交易逻辑 vs 中期配置逻辑

在对话中表达新的分析视角 → 系统自动写入 `memory/thinking-patterns/`。

---

## 📄 许可证

MIT License
