#!/usr/bin/env python3
"""Layer 2: Run bull-bear, dot-connecting, and catalyst analyses in parallel"""

import json, sys, io, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from grok_api import ask_deepseek

PROJECT = Path(__file__).parent.parent

def load_context():
    ctx_file = PROJECT / "output" / "l1_context.json"
    return json.loads(ctx_file.read_text(encoding="utf-8"))

def load_prompt(name):
    path = PROJECT / "prompts" / "deep-research" / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# 分析框架已内置在 system-base.md 中，无需额外加载

def run_bull_bear(ctx):
    system = load_prompt("system-base") + "\n\n" + load_prompt("bull-bear-arena")    prompt = f"""请基于以下第一层研究数据，构建每个市场的 Bull vs Bear 博弈框架。

## 第一层研究数据

### 半导体行业
{ctx["sector_semiconductor"]}

### AI行业
{ctx["sector_ai"]}

### 宏观与资金面
{ctx["macro_fundflow"]}

### 美股标的
{ctx["stocks_us"]}

### A股/港股
{ctx["stocks_cn"]}

### 加密货币
{ctx["crypto"]}

### 大V信号
{ctx["twitter"]}

---

请对以下四个市场，分别构建完整的多空博弈台：

## 🇺🇸 美股
### 🟢 多方逻辑（≥3条，引用具体证据）
### 🔴 空方逻辑（≥3条，引用具体证据）
### ⚡ 关键变量
### 🎯 我的判断（概率化）

## 🇨🇳 A股（同理）

## 🇭🇰 港股（同理）

## 🪙 加密货币（同理）

重要：
- 每条逻辑必须引用数据中的具体证据
- 给出有倾向性的判断(附概率)，不要骑墙
- 对6月5日暴跌给出多空双方的解读
- 用中文输出"""
    print("  ⚔️ 多空博弈台分析中...")
    return ask_deepseek(prompt, system=system, max_tokens=8000)

def run_dot_connecting(ctx):
    system = load_prompt("system-base") + "\n\n" + load_prompt("dot-connecting")    prompt = f"""请基于以下第一层研究数据，找到3-5条非显性的逻辑链。

## 全部研究数据

{json.dumps(ctx, ensure_ascii=False, indent=2)[:8000]}

---

请按照你的角色提示词，每条链包含：
1. 表面叙事 vs 深层逻辑
2. 证据链（A→B→C）
3. 历史镜鉴
4. 反身性思考
5. 置信度

关键推演方向：
- 6月5日暴跌是否可能是机构为SpaceX/Anthropic IPO出货换仓？
- 恐惧指数12+大V极度看空→是否已是反向买入信号？
- AI军备竞赛(GOOGL 800亿融资)与流动性收紧(加息预期)之间的矛盾如何演化？
- COMPUTEX的AI狂热与现实中的半导体抛售→是否意味着\"buy the rumor, sell the news\"？
- 北向资金6月初转流出→是短期调整还是趋势逆转？

用中文输出。大胆推理，但标注薄弱环节和置信度。"""
    print("  🔗 线索串联分析中...")
    return ask_deepseek(prompt, system=system, max_tokens=8000)

def run_catalyst(ctx):
    system = load_prompt("system-base") + "\n\n" + load_prompt("catalyst-scenario")    prompt = f"""请基于以下数据，对未来2周的关键事件做双向场景推演。

## 研究数据摘要

{json.dumps({k: ctx[k][:500] for k in ctx}, ensure_ascii=False)}

---

请至少覆盖以下事件：
1. ⭐ 6/8 Apple WWDC — Siri 2.0 + Google Gemini
2. ⭐ 6/12 SpaceX IPO (Nasdaq: SPCX) — 史上最大IPO
3. 6/24 美光Q3财报
4. 下次FOMC会议及CPI数据
5. Anthropic IPO进展
6. COMPUTEX后续影响

对每个事件：
- 偏多场景（什么算超预期？概率？影响哪些标的？）
- 中性场景
- 偏空场景（什么算低于预期？概率？影响哪些标的？）
- 定位启示

用中文输出。概率不要求和为100%。"""
    print("  📅 催化剂推演中...")
    return ask_deepseek(prompt, system=system, max_tokens=6000)

def main():
    ctx = load_context()

    print("🧠 Layer 2: 深度推演（并行3 agent）")
    print("=" * 50)

    tasks = {
        "bull_bear": ("多空博弈台", lambda: run_bull_bear(ctx)),
        "dot_connecting": ("线索串联", lambda: run_dot_connecting(ctx)),
        "catalyst": ("催化剂推演", lambda: run_catalyst(ctx)),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn): key for key, (name, fn) in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            name = tasks[key][0]
            try:
                result = future.result()
                results[key] = result
                print(f"  ✅ {name} 完成 ({len(result)} 字符)")
                sys.stdout.flush()
            except Exception as e:
                print(f"  ❌ {name} 失败: {e}")
                results[key] = f"分析失败: {e}"

    # Save results
    out_dir = PROJECT / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    for key, content in results.items():
        path = out_dir / f"l2_{key}.md"
        path.write_text(content, encoding="utf-8")

    print(f"\n✅ Layer 2 完成，结果已保存到 output/l2_*.md")

    # Also save combined JSON
    json_path = out_dir / "l2_results.json"
    json.dump(results, json_path, ensure_ascii=False, indent=2)
    print(f"✅ JSON 已保存到 {json_path}")

if __name__ == "__main__":
    main()
