/**
 * 每日股市研究 — 多智能体工作流
 *
 * 这是 mystock 系统的核心引擎。
 * 工作流分四个阶段：
 *   1. 解析需求单 — 读取 requirements.md
 *   2. 并行研究 — 启动多个智能体分别研究不同维度
 *   3. 汇总报告 — 将所有研究结果合并为一份日报
 *   4. 发送邮件 — 通过 Outlook/Exchange 发送报告
 *
 * 运行方式：在 Claude Code 中输入 "运行每日股市研究的 workflow"
 */

export const meta = {
  name: "每日股市研究",
  description: "多智能体并行研究全球股市（美股/A股/港股/加密货币），生成每日研究报告并发送邮件",
  phases: [
    { title: "解析需求单", detail: "读取 requirements.md 和 config.json，提取研究任务" },
    { title: "并行研究", detail: "技术面、新闻、宏观、资金流向、加密货币 — 多智能体同时搜索分析" },
    { title: "汇总报告", detail: "将所有研究结果合并、去重、排版，生成专业日报" },
    { title: "发送邮件", detail: "通过 Outlook/Exchange 将报告发送到指定邮箱" },
  ],
};

// ============================================================
// 阶段 1：解析需求单
// ============================================================
phase("解析需求单");

// Date.now()/new Date() are unavailable in workflow scripts — date must come from args
const today = (typeof args !== 'undefined' && args.date) ? args.date : "unknown-date";

const requirements = await agent(
  `请读取以下两个文件并解析内容：

1. requirements.md — 股市研究需求单
2. config.json — 项目配置

请提取以下信息并以 JSON 格式返回：
- stocks: 所有勾选 [x] 的关注标的，按市场分组（us/a_shares/hk/crypto）
- enabled_dimensions: 所有勾选 [x] 的研究维度
- custom_questions: 所有勾选 [x] 的自定义研究问题
- all_stocks_flat: 所有标的的展平列表（含代码和名称）

注意：
- [x] 表示启用，[ ] 表示禁用
- 只包含被勾选的项`,
  { label: "解析需求单", phase: "解析需求单", schema: {
    type: "object",
    properties: {
      stocks: {
        type: "object",
        properties: {
          us: { type: "array", items: { type: "object", properties: { code: { type: "string" }, name: { type: "string" } } } },
          a_shares: { type: "array", items: { type: "object", properties: { code: { type: "string" }, name: { type: "string" } } } },
          hk: { type: "array", items: { type: "object", properties: { code: { type: "string" }, name: { type: "string" } } } },
          crypto: { type: "array", items: { type: "object", properties: { code: { type: "string" }, name: { type: "string" } } } }
        }
      },
      enabled_dimensions: { type: "array", items: { type: "string" } },
      custom_questions: { type: "array", items: { type: "string" } },
      all_stocks_flat: { type: "array", items: { type: "string" } }
    },
    required: ["stocks", "enabled_dimensions", "custom_questions", "all_stocks_flat"]
  } }
);

log(`📋 需求单解析完成：共 ${requirements.all_stocks_flat.length} 个标的，${requirements.enabled_dimensions.length} 个研究维度，${requirements.custom_questions.length} 个自定义问题`);

// ============================================================
// 阶段 2：并行研究 — 所有研究维度同时启动
// ============================================================
phase("并行研究");

// 构建研究任务列表
const researchTasks = [];

// 技术面分析
if (requirements.enabled_dimensions.some(d => d.includes("技术面"))) {
  researchTasks.push({
    key: "技术面分析",
    prompt: `你是一位资深股票技术分析师。请对以下标的进行技术面分析。

${formatStocksByMarket(requirements.stocks)}

对每个标的，请通过网络搜索获取最新数据，提供：
1. **当前价格** — 最近交易日收盘价
2. **均线分析** — 5日/20日/60日均线位置，当前价格与均线的关系
3. **RSI(14)** — 数值及超买/超卖判断
4. **MACD** — DIF/DEA/柱状图状态，金叉/死叉信号
5. **关键支撑/阻力位** — 近期重要价位
6. **技术面判断** — 偏多/偏空/震荡，附简要理由

请用中文输出，每个标的的分析要具体、有数据支撑。`,
    label: "技术面分析",
  });
}

// 新闻与情绪
if (requirements.enabled_dimensions.some(d => d.includes("新闻"))) {
  researchTasks.push({
    key: "新闻与情绪",
    prompt: `你是一位金融市场新闻分析师。请搜索并汇总以下标的的今日重大新闻。

${formatStocksByMarket(requirements.stocks)}

搜索方向：
- 财报发布、业绩预告
- 分析师评级调整（升级/降级/目标价变动）
- 产品发布、重大合作
- 监管政策变动、法律诉讼
- 行业趋势和竞争格局

对每个标的，总结 2-5 条最重要的新闻，并给出情绪判断：
- 🟢 偏正面
- 🔴 偏负面
- 🟡 中性

请用中文输出。优先使用最新（24小时内）的信息。`,
    label: "新闻与情绪",
  });
}

// 宏观经济
if (requirements.enabled_dimensions.some(d => d.includes("宏观"))) {
  researchTasks.push({
    key: "宏观经济",
    prompt: `你是一位宏观经济学家。请搜索今天的关键宏观指标和市场背景。

请覆盖以下内容：

**美国市场**
- 美联储最新动态（官员讲话、政策信号）
- 最新利率预期（CME FedWatch）
- 10年期美债收益率
- VIX 恐慌指数
- 美元指数 (DXY)

**中国市场**
- 最新宏观数据（PMI、CPI、社融等）
- 央行政策动态
- 人民币汇率

**香港市场**
- 恒生指数走势
- 南向/北向资金概况

**大宗商品**
- 原油价格 (WTI/Brent)
- 黄金价格

最后，请分析这些宏观因素如何影响我们关注的标的。

请用中文输出，数据要有时效性。`,
    label: "宏观经济",
  });
}

// 资金流向
if (requirements.enabled_dimensions.some(d => d.includes("资金流向"))) {
  researchTasks.push({
    key: "资金流向",
    prompt: `你是一位资金流向分析专家。请搜索今日资金流向数据。

请覆盖：

**A股资金流向**
- 北向资金（沪股通+深股通）今日净流向及主要买卖标的
- 南向资金今日净流向
- 主力资金净流入/流出最多的板块

**美股资金流向**
- SPY/QQQ 等主要 ETF 的资金流入/流出
- 板块轮动情况（科技 vs 价值 vs 防御）

**港股资金流向**
- 南向资金的主要买卖方向

**加密货币**
- BTC ETF 资金流数据（如有）
- 稳定币流向

请用中文输出，尽量提供具体数字。`,
    label: "资金流向",
  });
}

// 加密货币
if (requirements.enabled_dimensions.some(d => d.includes("加密"))) {
  researchTasks.push({
    key: "加密货币",
    prompt: `你是一位加密货币分析师。请分析今日加密市场状况。

请搜索并输出：

1. **BTC 行情**
   - 当前价格、24h涨跌幅
   - 技术面：关键支撑/阻力位、趋势判断
   - BTC 市占率 (Dominance)

2. **ETH 行情**
   - 当前价格、24h涨跌幅
   - ETH/BTC 汇率

3. **市场情绪**
   - 恐惧与贪婪指数 (Fear & Greed Index)
   - 全网合约持仓量、爆仓数据

4. **重大新闻**
   - 监管动态（SEC、香港、欧盟等）
   - 机构采用（ETF资金流、企业买入）
   - 链上数据亮点

5. **其他值得关注的代币**（如有重大异动）

请用中文输出。`,
    label: "加密货币",
  });
}

// 自定义研究问题
requirements.custom_questions.forEach((q, i) => {
  researchTasks.push({
    key: `自定义研究 ${i + 1}`,
    prompt: `请深入调研以下问题：

"${q}"

要求：
- 搜索多个来源，交叉验证信息
- 给出有深度的分析，不只是罗列事实
- 如果涉及政策，说明对市场的潜在影响
- 用中文输出`,
    label: `自定义问题${i + 1}`,
  });
});

log(`🚀 启动 ${researchTasks.length} 个并行研究智能体...`);

// 所有研究任务并行执行
const researchResults = await parallel(
  researchTasks.map(task => () =>
    agent(task.prompt, {
      label: task.label,
      phase: "并行研究",
    }).then(content => ({ key: task.key, content }))
  )
);

log(`✅ 所有研究智能体已完成工作`);

// ============================================================
// 阶段 3：汇总报告
// ============================================================
phase("汇总报告");

const reportPrompt = `你是一位资深财经编辑。请将以下多维度研究结果整合为一份专业的每日股市研究报告。

## 研究原始数据

${researchResults.filter(Boolean).map(r => `
### ${r.key}
${r.content}
---
`).join("\n")}

## 报告要求

请严格按照以下格式输出完整报告，保存到 output/${today}-股市日报.md：

---

# 📈 每日股市研究报告

**日期**：${today}
**生成时间**：${typeof args !== 'undefined' && args.now ? args.now : "unknown"}

---

## 📊 市场概览

[200-300字总结今日全球市场整体情况：美股/A股/港股/加密货币的主要走势和关键主题]

---

## 🔍 标的深度分析

### 🇺🇸 美股

对每个关注的美股标的，整合技术面和新闻信息，给出：
- **当前价格与技术面判断**
- **今日关键新闻**
- **综合情绪**：🟢/🔴/🟡
- **短期展望**（1-2句话）

### 🇨🇳 A股

同理覆盖每个A股标的

### 🇭🇰 港股

同理覆盖每个港股标的

---

## 🪙 加密货币专题

[BTC/ETH的详细分析]

---

## 📰 重大新闻与市场情绪

[今日最重要的市场新闻汇总，按重要性排列]

---

## 🏛 宏观经济观察

[宏观经济数据和政策动态]

---

## 💰 资金流向

[北向/南向资金、ETF资金流、板块轮动]

---

## 📝 自定义研究

[逐一回答需求单中的自定义问题]

---

## ⚠️ 风险提示

[列出未来1-2周需要关注的风险事件]

---

> 🤖 本报告由 AI 多智能体系统（Claude Code Multi-Agent）自动生成，仅供参考，不构成投资建议。
> 📅 下一个交易日的研究报告将自动生成并发送。

---

请确保：
1. 每个标的都有实质性分析，不要遗漏
2. 数据要有具体数字支撑，不要泛泛而谈
3. 使用中文撰写，专业术语保留英文
4. 格式整洁，层级清晰
5. 用 Write 工具将完整报告写入 output/${today}-股市日报.md
6. 返回报告的 Markdown 完整内容`;

const report = await agent(reportPrompt, {
  label: "汇总报告",
  phase: "汇总报告",
});

log(`📝 报告已生成并保存到 output/${today}-股市日报.md`);

// ============================================================
// 阶段 4：发送邮件
// ============================================================
phase("发送邮件");

await agent(
  `请运行以下命令将报告发送到邮箱：

python scripts/send_email.py --subject "📈 每日股市研究报告 - ${today}" --file "output/${today}-股市日报.md"

如果发送失败，请检查：
- 是否设置了环境变量 MYSTOCK_EMAIL_USER 和 MYSTOCK_EMAIL_PASS
- 或者 config.json 中 use_outlook_com 是否设为 true（如果使用本地 Outlook）
- Python 依赖是否安装：pip install pywin32

请执行命令并报告发送结果。`,
  { label: "发送邮件", phase: "发送邮件" }
);

log("🎉 每日股市研究完成！报告已生成并发送到邮箱。");

// ============================================================
// 辅助函数
// ============================================================
function formatStocksByMarket(stocks) {
  const parts = [];
  if (stocks.us?.length) {
    parts.push("### 美股\n" + stocks.us.map(s => `- ${s.code} (${s.name})`).join("\n"));
  }
  if (stocks.a_shares?.length) {
    parts.push("### A股\n" + stocks.a_shares.map(s => `- ${s.code} (${s.name})`).join("\n"));
  }
  if (stocks.hk?.length) {
    parts.push("### 港股\n" + stocks.hk.map(s => `- ${s.code} (${s.name})`).join("\n"));
  }
  if (stocks.crypto?.length) {
    parts.push("### 加密货币\n" + stocks.crypto.map(s => `- ${s.code} (${s.name})`).join("\n"));
  }
  return parts.join("\n\n");
}
