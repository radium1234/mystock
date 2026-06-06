#!/usr/bin/env python3
"""
mystock 深度研究执行脚本 — 三层递进思考引擎

架构：
  第一层（并行5 agents）：板块搜索 | 个股搜索 | 宏观资金面 | 大V推文 | 加密货币
  第二层（并行3 agents）：多空博弈台 | 线索串联 | 催化剂场景推演
  第三层（串行）：主笔撰写 HTML 报告 → 发送邮件

用法：
  python scripts/run_deep_research.py              # 完整运行
  python scripts/run_deep_research.py --no-email   # 不发送邮件
  python scripts/run_deep_research.py --save-json  # 保存中间结果
"""

import os
import sys
import json
import time
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# Setup
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Import existing API helpers
from grok_api import ask_deepseek, ask_twitter_grok, search_twitter_api

# Timezone
CST = timezone(timedelta(hours=8))

# ============================================================
# Prompt loading
# ============================================================
def load_prompt(name):
    """Load a prompt template from prompts/deep-research/"""
    path = PROJECT_ROOT / "prompts" / "deep-research" / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

def build_system_prompt(role_prompt_name):
    """Build a complete system prompt: base (contains analysis frameworks) + role-specific"""
    base = load_prompt("system-base")
    role = load_prompt(role_prompt_name)
    # 分析框架已内置在 system-base.md 中，无需额外加载
    return "\n\n".join([base, role])

# ============================================================
# Requirements parsing
# ============================================================
def parse_requirements():
    """Parse requirements.md to extract enabled stocks, dimensions, questions"""
    req_file = PROJECT_ROOT / "requirements.md"
    if not req_file.exists():
        return {"stocks": {}, "dimensions": [], "questions": [], "twitter_users": []}

    content = req_file.read_text(encoding="utf-8")

    stocks = {"us": [], "a_shares": [], "hk": [], "crypto": []}
    dimensions = []
    questions = []
    twitter_users = []
    current_market = None
    in_twitter = False
    in_questions = False

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect sections
        if "美股" in line and "###" in line:
            current_market = "us"
            continue
        elif "A股" in line and "###" in line:
            current_market = "a_shares"
            continue
        elif "港股" in line and "###" in line:
            current_market = "hk"
            continue
        elif "加密货币" in line and "###" in line:
            current_market = "crypto"
            continue
        elif "大V推特" in line and "##" in line:
            in_twitter = True
            continue
        elif "自定义研究" in line and "##" in line:
            in_questions = True
            continue
        elif "市场预测" in line and "##" in line:
            in_questions = False
            continue

        # Parse checked items
        if line.startswith("- [x]") or line.startswith("- [X]"):
            item = line[5:].strip()

            if in_twitter:
                # Extract twitter username
                import re
                match = re.search(r'@(\w+)', item)
                if match:
                    twitter_users.append(match.group(1))
                continue

            if in_questions:
                questions.append(item)
                continue

            # Stock items
            if current_market and ("(" in item or "（" in item):
                # Parse "CODE (Name)" or "Name (CODE)"
                import re
                # Try pattern: CODE (Name)
                match = re.match(r'([A-Za-z0-9.]+)\s*[（(](.+?)[）)]', item)
                if match:
                    code, name = match.groups()
                    stocks[current_market].append({"code": code.strip(), "name": name.strip()})
                else:
                    # Try pattern: Name — CODE or similar
                    stocks[current_market].append({"code": item, "name": item})

            # Dimension items
            if "**" in item:
                dim_name = re.sub(r'\*\*|\*', '', item.split("—")[0].strip())
                dimensions.append(dim_name)

    return {
        "stocks": stocks,
        "dimensions": dimensions,
        "questions": questions,
        "twitter_users": twitter_users,
    }

# ============================================================
# Layer 1: Information Gathering (Parallel)
# ============================================================
def agent_sector_deep(req):
    """Agent 1: Deep sector search (Semiconductor + AI)"""
    print("  🔬 [1/5] 板块深度搜索（半导体 + AI）...")
    sys.stdout.flush()
    system = build_system_prompt("sector-deep")
    prompt = f"""请深度搜索并分析半导体和AI行业的最新动态（2026年6月初）。

关注标的背景：
- 美股半导体：NVDA, MU (美光5月暴涨87%), AMD
- A股半导体：002463 沪电股份（PCB龙头，Q1营收62亿+53.9%）
- AI：GOOGL (800亿融资+AI基建), MSFT, META, AMZN

请按照你的角色提示词，给出每条新闻的：
1. 事实摘要（~200字）
2. 多方解读
3. 空方解读
4. 第二层影响

重点关注：COMPUTEX 2026 后续、HBM 供需、WWDC前夕 AI 预期、SpaceX AI算力合作"""
    return {"key": "板块深度", "content": ask_deepseek(prompt, system=system, max_tokens=6000)}

def agent_stock_deep(req):
    """Agent 2: Individual stock deep search"""
    print("  📈 [2/5] 个股深度搜索...")
    sys.stdout.flush()
    system = build_system_prompt("stock-deep")

    all_stocks = []
    for market, stocks_list in req["stocks"].items():
        if stocks_list:
            market_names = {"us": "美股", "a_shares": "A股", "hk": "港股", "crypto": "加密货币"}
            all_stocks.append(f"### {market_names.get(market, market)}")
            for s in stocks_list:
                all_stocks.append(f"- {s['code']} ({s['name']})")

    stock_list = "\n".join(all_stocks)

    prompt = f"""请对以下标的进行深度信息搜集和分析：

{stock_list}

对每个标的，按以下结构输出：
1. **最新动态**（3-5条，每条~150字）
2. **🟢 多方论点**（至少3条，有证据）
3. **🔴 空方论点**（至少3条，有证据）
4. **⚡ 关键触发器**（什么事件会引爆多/空？）

特别关注：
- MU：5月暴涨87%后回调13%，6/24财报，目标价升至$1625
- GOOGL：800亿融资（史上最大），伯克希尔认购100亿，CapEx 1800-1900亿
- 002463 沪电股份：港股IPO递表，订单看到2027年，机构密集调研
- AAPL：6/8 WWDC，Siri接入Gemini
- NVDA：COMPUTEX Vera Rubin量产，HBM4E"""
    return {"key": "个股深度", "content": ask_deepseek(prompt, system=system, max_tokens=8000)}

def agent_macro(req):
    """Agent 3: Macro & fund flow"""
    print("  🏛 [3/5] 宏观与资金面分析...")
    sys.stdout.flush()
    system = build_system_prompt("macro-fundflow")
    prompt = """请分析当前（2026年6月7日前后）的全球宏观环境和资金流向。

重点问题：
1. 上周五（6/5）非农数据后，市场为何暴跌？加息预期如何变化？
2. 10年期美债收益率和VIX的最新水平？
3. 北向资金和南向资金的最新流向？
4. SPY/QQQ ETF资金流情况？
5. 美元指数和大宗商品走势？

对每个数据点，给出「多空双方各自会怎么解读」。"""
    return {"key": "宏观资金面", "content": ask_deepseek(prompt, system=system, max_tokens=6000)}

def agent_twitter(req):
    """Agent 4: Twitter/X analysis via Grok + X API"""
    print("  📡 [4/5] 大V推文抓取与分析...")
    sys.stdout.flush()

    users = req.get("twitter_users", ["aleabitoreddit", "bboczeng"])
    results = {}

    for username in users:
        try:
            print(f"    🔍 搜索 @{username} ...")
            sys.stdout.flush()
            analysis = ask_twitter_grok(
                f"请分析 @{username} 最近24小时的推文。\n\n"
                f"对每条重要推文，不只总结内容，还要分析：\n"
                f"1. 他真正想表达什么？（话外之音）\n"
                f"2. 他的情绪处于什么极端水平？（极度看空/看多？）\n"
                f"3. 反向阅读：如果他的极端情绪是反向指标，意味着什么？\n"
                f"4. 对他的关注标的（如果有）给出操作启示\n\n"
                f"用中文输出。",
                max_tokens=3000
            )
            results[username] = analysis
        except Exception as e:
            print(f"    ⚠️ @{username} 分析失败: {e}")
            results[username] = f"（分析失败：{e}）"

    combined = "\n\n".join([f"## @{u}\n{a}" for u, a in results.items()])
    return {"key": "大V推文", "content": combined}

def agent_crypto(req):
    """Agent 5: Cryptocurrency analysis"""
    print("  🪙 [5/5] 加密货币专项分析...")
    sys.stdout.flush()
    system = build_system_prompt("crypto-deep")

    crypto_stocks = req["stocks"].get("crypto", [])
    symbols = [s["code"] for s in crypto_stocks] if crypto_stocks else ["BTC", "ETH"]

    prompt = f"""请深度分析以下加密货币的最新情况：{', '.join(symbols)}

请按你的角色提示词，给出：
1. 价格/技术面/链上数据
2. 多空观点分明
3. 短期（1周）和中期（1-3月）判断
4. 极端情绪信号分析

特别关注：BTC与纳斯达克相关性变化、ETF资金流。"""
    return {"key": "加密货币", "content": ask_deepseek(prompt, system=system, max_tokens=4000)}

# ============================================================
# Layer 2: Deep Analysis (Parallel)
# ============================================================
def agent_bull_bear(layer1_context):
    """Agent 6: Bull vs Bear arena"""
    print("  ⚔️ [6/8] 多空博弈台构建...")
    sys.stdout.flush()
    system = build_system_prompt("bull-bear-arena")
    prompt = f"""请基于以下第一层研究数据，构建每个市场的 Bull vs Bear 博弈框架：

## 第一层研究数据

{layer1_context}

请对美股、A股、港股、加密货币分别构建完整的多空博弈逻辑。
每个市场必须包含：
- 多方逻辑（≥3条，引用数据中的具体证据）
- 空方逻辑（≥3条，引用数据中的具体证据）
- 关键变量（什么会打破平衡）
- 我的判断（概率化，有倾向性，不骑墙）

这是报告中最重要的部分，请尽可能深入。"""
    return {"key": "多空博弈台", "content": ask_deepseek(prompt, system=system, max_tokens=8000)}

def agent_dot_connecting(layer1_context):
    """Agent 7: Connect the dots"""
    print("  🔗 [7/8] 线索串联与深度推演...")
    sys.stdout.flush()
    system = build_system_prompt("dot-connecting")
    prompt = f"""请基于以下第一层研究数据，找到 3-5 条非显性的逻辑链：

## 第一层研究数据

{layer1_context}

请按照你的角色提示词，每条链包含：
- 表面叙事 vs 深层逻辑
- 证据链（A→B→C）
- 历史镜鉴
- 反身性思考
- 置信度

注意：用户特别关注——
1. 周五暴跌是否可能是机构为 SpaceX/Anthropic IPO 出货换仓？
2. 大V极度看空的情绪是否已经是反向买入信号？
3. AI军备竞赛（GOOGL 800亿融资）与市场流动性收紧之间的矛盾如何演化？

每条链要有数据支撑，不是凭空编造。但也不要保守——大胆推理，诚实标注薄弱环节。"""
    return {"key": "线索串联", "content": ask_deepseek(prompt, system=system, max_tokens=8000)}

def agent_catalyst(layer1_context):
    """Agent 8: Forward catalyst scenarios"""
    print("  📅 [8/8] 前瞻催化剂场景推演...")
    sys.stdout.flush()
    system = build_system_prompt("catalyst-scenario")
    prompt = f"""请基于以下第一层研究数据，对未来2周的关键事件做双向场景推演：

## 第一层研究数据

{layer1_context}

至少覆盖以下事件（如适用）：
1. 6/8 Apple WWDC — Siri+Gemini
2. 6/24 美光 Q3 财报
3. 下次 FOMC 会议及 CPI 数据
4. SpaceX / Anthropic IPO 进展
5. COMPUTEX 后续影响
6. 其他你发现的关键事件

对每个事件：偏多场景 + 中性场景 + 偏空场景，附概率和具体标的影响。"""
    return {"key": "催化剂推演", "content": ask_deepseek(prompt, system=system, max_tokens=6000)}

# ============================================================
# Layer 3: Report Assembly
# ============================================================
def assemble_html_report(layer1_results, layer2_results, date_str):
    """Agent 9: Master writer — assemble the final HTML report"""
    print("  📝 [9/10] 主笔撰写报告...")
    sys.stdout.flush()

    # Build context JSON for the writer
    l1_summary = {}
    for r in layer1_results:
        if r:
            l1_summary[r["key"]] = r["content"][:3000]  # Truncate for prompt size

    l2_summary = {}
    for r in layer2_results:
        if r:
            l2_summary[r["key"]] = r["content"]

    # Load HTML template
    template = (PROJECT_ROOT / "templates" / "deep-report.html").read_text(encoding="utf-8")

    system = f"""你是一位资深财经主编。你的任务是将深度研究数据整合为一份高质量的 HTML 股市研报。

## HTML 模板说明

报告使用以下模板结构（用 {{{{SECTION_NAME}}}} 标记占位）：

{template}

## 写作要求

1. **直接写入占位标记** — 你的输出中每个 {{{{SECTION_NAME}}}} 会被替换为对应的 HTML 内容
2. **使用模板中的 CSS class** — 多空博弈台用 `arena`/`arena-bull`/`arena-bear`，线索串联用 `clue-card`，标的分析用 `stock-card`，催化剂用表格，风险矩阵用 `risk-grid`
3. **深度分析** — 每个部分都是多空双视角，不罗列事实
4. **概率化** — 判断要有概率，不骑墙
5. **可操作** — 最后的操作启示要具体到「如果X，就做Y」
6. **超链接** — 如有来源URL，保留超链接

请严格按以下格式输出。每个 SECTION 用 `===== SECTION_NAME =====` 标记，然后是完整的 HTML 内容。

输出格式：
```
===== CORE_NARRATIVE =====
（今日核心推演的完整 HTML，包括 narrative 和 verdict）

===== BULL_BEAR_ARENA =====
（美股/A股/港股/加密货币 多空博弈台的完整 HTML）

===== DOT_CONNECTING =====
（线索串联的完整 HTML）

===== CATALYST_SCENARIOS =====
（催化剂场景推演表格的完整 HTML）

===== STOCK_DEEP_DIVE =====
（标的深度分析的完整 HTML）

===== INFLUENCER_SIGNALS =====
（大V信号解读的完整 HTML）

===== CRYPTO_SECTION =====
（加密货币专题的完整 HTML）

===== RISK_MATRIX =====
（风险矩阵的完整 HTML）

===== PLAYBOOK =====
（操作启示的完整 HTML）
```

请生成所有部分的完整 HTML 内容。每个部分的 CSS class 必须与模板匹配。"""

    prompt = f"""请基于以下研究数据，生成完整深度研报的所有 HTML 部分。

## 日期
{date_str}

## 第一层：原始研究数据

### 板块深度
{l1_summary.get("板块深度", "（暂无）")}

### 个股深度
{l1_summary.get("个股深度", "（暂无）")}

### 宏观与资金面
{l1_summary.get("宏观资金面", "（暂无）")}

### 大V推文分析
{l1_summary.get("大V推文", "（暂无）")}

### 加密货币
{l1_summary.get("加密货币", "（暂无）")}

## 第二层：深度分析

### 多空博弈台
{l2_summary.get("多空博弈台", "（暂无）")}

### 线索串联
{l2_summary.get("线索串联", "（暂无）")}

### 催化剂推演
{l2_summary.get("催化剂推演", "（暂无）")}

请严格按格式输出所有 SECTION 的完整 HTML。"""

    content = ask_deepseek(prompt, system=system, max_tokens=12000)

    # Parse sections from the response
    sections = {}
    current_section = None
    current_content = []

    for line in content.splitlines():
        if line.startswith("=====") and line.endswith("====="):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line.strip("= ").strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Fill template
    html = template
    placeholders = [
        "CORE_NARRATIVE", "BULL_BEAR_ARENA", "DOT_CONNECTING",
        "CATALYST_SCENARIOS", "STOCK_DEEP_DIVE", "INFLUENCER_SIGNALS",
        "CRYPTO_SECTION", "RISK_MATRIX", "PLAYBOOK"
    ]

    for ph in placeholders:
        content = sections.get(ph, f"<p style='color:var(--sub);'>({ph} 数据暂缺)</p>")
        html = html.replace("{{" + ph + "}}", content)

    # Replace date
    html = html.replace("{{DATE}}", date_str)

    # Save
    date_tag = datetime.now(CST).strftime("%Y-%m-%d")
    output_path = PROJECT_ROOT / "output" / f"{date_tag}-深度研报.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"  ✅ 报告已保存: {output_path}")
    sys.stdout.flush()

    return str(output_path)

# ============================================================
# Layer 3b: Send Email
# ============================================================
def send_email(report_path, date_str):
    """Send the report via QQ email"""
    print("  📧 [10/10] 发送邮件...")
    sys.stdout.flush()

    import subprocess
    send_script = PROJECT_ROOT / "scripts" / "send_email.py"

    # Read the HTML content
    html_content = Path(report_path).read_text(encoding="utf-8")

    # Write subject line and call send_email.py
    subject = f"📊 mystock 深度研报 - {date_str}"

    try:
        result = subprocess.run(
            [sys.executable, str(send_script), "--subject", subject, "--body", html_content],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT)
        )
        if result.returncode == 0:
            print(f"  ✅ 邮件发送成功！")
            return True
        else:
            print(f"  ⚠️ 邮件发送可能失败:\n{result.stderr[:500]}")
            return False
    except Exception as e:
        print(f"  ❌ 邮件发送异常: {e}")
        return False

# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="🧠 mystock 深度研究引擎")
    parser.add_argument("--no-email", action="store_true", help="不发送邮件")
    parser.add_argument("--save-json", action="store_true", help="保存中间JSON结果")
    parser.add_argument("--no-twitter", action="store_true", help="跳过推特搜索")
    args = parser.parse_args()

    date_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M CST")
    date_tag = datetime.now(CST).strftime("%Y-%m-%d")

    print(f"""
╔══════════════════════════════════════════╗
║   🧠 mystock 深度研究引擎 v2.0         ║
║   三层递进思考 · 多空博弈 · 线索串联    ║
║   {date_str}                        ║
╚══════════════════════════════════════════╝
""")
    sys.stdout.flush()

    # Step 0: Parse requirements
    print("📋 解析需求单...")
    req = parse_requirements()
    print(f"   美股 {len(req['stocks'].get('us',[]))} 只 | A股 {len(req['stocks'].get('a_shares',[]))} 只 | 港股 {len(req['stocks'].get('hk',[]))} 只 | 加密货币 {len(req['stocks'].get('crypto',[]))} 只")
    print(f"   大V {len(req.get('twitter_users',[]))} 位 | 自定义问题 {len(req.get('questions',[]))} 个")
    sys.stdout.flush()

    t_start = time.time()

    # ========================================
    # Layer 1: Parallel information gathering
    # ========================================
    print("\n{'='*50}")
    print("📡 第一层：信息采集（并行5 agent）")
    print("=" * 50)

    layer1_tasks = [
        ("板块深度", lambda: agent_sector_deep(req)),
        ("个股深度", lambda: agent_stock_deep(req)),
        ("宏观资金面", lambda: agent_macro(req)),
        ("大V推文", lambda: agent_twitter(req) if not args.no_twitter else {"key": "大V推文", "content": "（已跳过）"}),
        ("加密货币", lambda: agent_crypto(req)),
    ]

    layer1_results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(task[1]): task[0] for task in layer1_tasks}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                layer1_results.append(result)
                content_len = len(result.get("content", "")) if result else 0
                print(f"  ✅ {name} 完成 ({content_len} 字符)")
                sys.stdout.flush()
            except Exception as e:
                print(f"  ❌ {name} 失败: {e}")
                layer1_results.append({"key": name, "content": f"（分析失败：{e}）"})

    t1 = time.time()
    print(f"\n⏱ 第一层耗时: {t1 - t_start:.0f}秒")

    # Build context for layer 2
    l1_context = "\n\n".join([
        f"## {r['key']}\n{r['content'][:4000]}" for r in layer1_results if r
    ])

    # ========================================
    # Layer 2: Parallel deep analysis
    # ========================================
    print(f"\n{'='*50}")
    print("🧠 第二层：深度推演（并行3 agent）")
    print("=" * 50)

    layer2_tasks = [
        ("多空博弈台", lambda: agent_bull_bear(l1_context)),
        ("线索串联", lambda: agent_dot_connecting(l1_context)),
        ("催化剂推演", lambda: agent_catalyst(l1_context)),
    ]

    layer2_results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(task[1]): task[0] for task in layer2_tasks}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                layer2_results.append(result)
                content_len = len(result.get("content", "")) if result else 0
                print(f"  ✅ {name} 完成 ({content_len} 字符)")
                sys.stdout.flush()
            except Exception as e:
                print(f"  ❌ {name} 失败: {e}")
                layer2_results.append({"key": name, "content": f"（分析失败：{e}）"})

    t2 = time.time()
    print(f"\n⏱ 第二层耗时: {t2 - t1:.0f}秒")

    # ========================================
    # Layer 3: Report assembly + email
    # ========================================
    print(f"\n{'='*50}")
    print("📝 第三层：报告撰写与发送")
    print("=" * 50)

    report_path = assemble_html_report(layer1_results, layer2_results, date_str)

    email_sent = False
    if not args.no_email:
        email_sent = send_email(report_path, date_str)

    t3 = time.time()
    print(f"\n⏱ 第三层耗时: {t3 - t2:.0f}秒")

    # ========================================
    # Save intermediate results if requested
    # ========================================
    if args.save_json:
        json_path = PROJECT_ROOT / "output" / f"{date_tag}-raw-data.json"
        data = {
            "date": date_str,
            "layer1": [{"key": r["key"], "content_len": len(r["content"])} for r in layer1_results if r],
            "layer2": [{"key": r["key"], "content_len": len(r["content"])} for r in layer2_results if r],
        }
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📦 中间数据已保存: {json_path}")

    # ========================================
    # Summary
    # ========================================
    total = time.time() - t_start
    print(f"""
╔══════════════════════════════════════════╗
║   🎉 深度研究完成！                    ║
║   总耗时: {total:.0f}秒 ({total/60:.1f}分钟)            ║
║   报告: {report_path}  ║
║   邮件: {'✅ 已发送' if email_sent else '⏭ 已跳过'}                        ║
╚══════════════════════════════════════════╝
""")

    return report_path

if __name__ == "__main__":
    main()
