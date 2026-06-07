#!/usr/bin/env python3
"""
mystock API 助手 — 直连 DeepSeek 和 xAI 官方 API

用法：
  python scripts/grok_api.py "你的问题"           # 默认 DeepSeek V4 Flash
  python scripts/grok_api.py --x-query "from:user" # 只调用 X API，不调用 AI
  python scripts/grok_api.py --x-user username     # 只搜索指定用户最近推文，不调用 AI
  python scripts/grok_api.py --xai --search "..."  # 旧兼容：Grok + X API 搜推特
  python scripts/grok_api.py --xai "直接问 Grok"   # 直调 Grok（仅推特场景）

模型策略（配置在 .env）：
  - DEEPSEEK_MODEL=deepseek-v4-flash    → 通用分析/预测/报告（DeepSeek 直连，国内免代理）
  - XAI_MODEL=grok-4.20             → X/Twitter 数据抓取（xAI 直连，需 Clash 代理）
  - Grok 不参与分析，仅抓取信息

环境变量（.env）：
  DEEPSEEK_API_KEY — DeepSeek 官方 API key
  XAI_API_KEY      — xAI 官方 API key
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# 自动从 .env 加载环境变量
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# ---------- DeepSeek 官方 API ----------

DEEPSEEK_BASE = "https://api.deepseek.com/v1/chat/completions"


def _load_env(key):
    """Read a value from environment, falling back to .env file."""
    val = os.environ.get(key)
    if val:
        return val
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def ask_deepseek(prompt, system=None, max_tokens=4000, temperature=0.7):
    """调用 DeepSeek 官方 API（国内直连，无需代理）"""
    api_key = _load_env("DEEPSEEK_API_KEY")
    if not api_key:
        raise Exception("未设置 DEEPSEEK_API_KEY，请在 .env 中配置")

    model = _load_env("DEEPSEEK_MODEL") or "deepseek-v4-flash"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        DEEPSEEK_BASE,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"DeepSeek API Error [{e.code}]: {err_body}")


# ---------- xAI 官方 API ----------

XAI_BASE = "https://api.x.ai/v1/chat/completions"


def ask_xai(prompt, system=None, max_tokens=4000, temperature=0.7, tools=None, tool_choice="auto"):
    """调用 xAI 官方 API（需 Clash 代理）"""
    api_key = _load_env("XAI_API_KEY")
    if not api_key:
        raise Exception("未设置 XAI_API_KEY，请在 .env 中配置")

    model = _load_env("XAI_MODEL") or "grok-4.20"

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        XAI_BASE,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"xAI API Error [{e.code}]: {err_body}")


# ---------- X/Twitter API v2 ----------

def search_twitter_api(query, max_results=10):
    """通过 Twitter API v2 搜索推文"""
    bearer = _load_env("TWITTER_BEARER_TOKEN")
    if not bearer:
        raise Exception("未设置 TWITTER_BEARER_TOKEN")

    import urllib.parse
    url = (
        f"https://api.twitter.com/2/tweets/search/recent"
        f"?query={urllib.parse.quote(query)}"
        f"&max_results={max_results}"
        f"&tweet.fields=created_at,public_metrics,author_id"
        f"&expansions=author_id"
        f"&user.fields=username,name"
    )

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer}"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

        results = []
        for t in tweets:
            author = users.get(t.get("author_id"), {})
            results.append({
                "text": t["text"],
                "username": author.get("username", "unknown"),
                "date": t.get("created_at", ""),
                "likes": t.get("public_metrics", {}).get("like_count", 0),
                "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
            })
        return results
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"X API Error [{e.code}]: {err_body}")


def search_twitter_user(username, max_results=10):
    """Deterministic X API capability: recent tweets from one user."""
    username = username.lstrip("@")
    return search_twitter_api(f"from:{username} -is:retweet", max_results=max_results)


def format_tweets(tweets):
    """Format raw X API tweets for terminal or prompt input."""
    if not tweets:
        return "（无搜索结果）"
    lines = []
    for idx, tweet in enumerate(tweets, 1):
        if "error" in tweet:
            lines.append(f"{idx}. 搜索失败：{tweet['error']}")
            continue
        lines.append(
            f"{idx}. @{tweet.get('username', 'unknown')} | {tweet.get('date', '')} | "
            f"likes={tweet.get('likes', 0)} retweets={tweet.get('retweets', 0)}\n"
            f"{tweet.get('text', '')}"
        )
    return "\n\n".join(lines)


# ---------- Grok + X API 旧兼容路径 ----------

def ask_twitter_grok(prompt, max_tokens=4000):
    """用 Grok (xAI API) + x_search 工具 → X API 搜索 → Grok 分析（仅抓取）"""
    tools = [{
        "type": "function",
        "function": {
            "name": "x_search",
            "description": "Search X/Twitter for recent tweets and posts",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "X search query (supports from:username, keyword, etc.)"}
                },
                "required": ["query"]
            }
        }
    }]

    system = "你是推特数据抓取助手。你只负责搜索和整理推文，不做分析判断。用中文输出。"

    # Step 1: 让 Grok 生成搜索词
    result = ask_xai(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice="auto",
    )

    msg = result.get("choices", [{}])[0].get("message", {})
    tool_calls = msg.get("tool_calls")

    if not tool_calls:
        return msg.get("content") or "（模型未发起搜索）"

    # Step 2: 解析搜索词
    tc = tool_calls[0]
    args = json.loads(tc["function"]["arguments"])
    query = args.get("query", "")
    print(f"  🔍 搜索: {query}")
    sys.stdout.flush()

    # Step 3: 通过 X API 搜索
    try:
        tweets = search_twitter_api(query, max_results=15)
    except Exception as e:
        print(f"  ⚠️ X API 搜索失败: {e}")
        return f"X API 搜索失败: {e}"

    print(f"  ✅ 找到 {len(tweets)} 条推文")
    sys.stdout.flush()

    # Step 4: 返回搜索结果给 Grok 整理
    tweets_json = json.dumps({"tweets": tweets}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        msg,
        {"role": "tool", "tool_call_id": tc["id"], "content": tweets_json}
    ]

    model = _load_env("XAI_MODEL") or "grok-4.20"
    body = {"model": model, "messages": messages, "max_tokens": max_tokens}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        XAI_BASE, data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {_load_env('XAI_API_KEY')}",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        result2 = json.loads(resp.read())
        return result2.get("choices", [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"xAI API Error [{e.code}]: {err_body}")


# ---------- CLI ----------

def main():
    import argparse

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="🤖 mystock API 助手")
    parser.add_argument("prompt", nargs="?", help="输入问题（默认调用 DeepSeek）")
    parser.add_argument("--x-query", help="只调用 X API recent search，不调用 AI")
    parser.add_argument("--x-user", help="只搜索指定 X/Twitter 用户最近推文，不调用 AI")
    parser.add_argument("--json", action="store_true", help="能力模式下输出 JSON")
    parser.add_argument("--max-results", type=int, default=10, help="X API 最大返回条数")
    parser.add_argument("--xai", action="store_true", help="使用 xAI Grok API（需代理）")
    parser.add_argument("--search", "-s", action="store_true", help="启用 x_search 工具搜索 X/Twitter")
    parser.add_argument("--system", help="系统提示词")
    parser.add_argument("--file", "-f", help="从文件读取输入")
    parser.add_argument("--save", help="输出保存到文件")
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--list-models", action="store_true", help="显示当前模型配置")

    args = parser.parse_args()

    if args.list_models:
        ds_model = _load_env("DEEPSEEK_MODEL") or "deepseek-v4-flash"
        xai_model = _load_env("XAI_MODEL") or "grok-4.20"
        print(f"""
📋 当前模型配置（来自 .env）：

  通用分析 → DeepSeek 直连
    模型: {ds_model}
    API:  {DEEPSEEK_BASE}
    代理: 不需要（国内直连）

  推特抓取 → xAI 直连
    模型: {xai_model}
    API:  {XAI_BASE}
    代理: 需要 Clash (127.0.0.1:7897)

  X/Twitter 搜索 → X API v2
    配额: 基础版免费
""")
        return

    # Pure capability modes: no AI call, only X API.
    if args.x_query:
        tweets = search_twitter_api(args.x_query, max_results=args.max_results)
        if args.json:
            print(json.dumps({"query": args.x_query, "tweets": tweets}, ensure_ascii=False, indent=2))
        else:
            print(format_tweets(tweets))
        return

    if args.x_user:
        tweets = search_twitter_user(args.x_user, max_results=args.max_results)
        if args.json:
            print(json.dumps({"user": args.x_user.lstrip("@"), "tweets": tweets}, ensure_ascii=False, indent=2))
        else:
            print(format_tweets(tweets))
        return

    # 读取输入
    prompt = args.prompt
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            prompt = f.read()
    if not prompt:
        print("❌ 请提供问题")
        parser.print_help()
        sys.exit(1)

    # 路由请求
    if args.xai:
        if args.search:
            print("🤖 调用 Grok + x_search 抓取推特 ...")
            sys.stdout.flush()
            content = ask_twitter_grok(prompt, max_tokens=args.max_tokens)
        else:
            print("🤖 调用 Grok（仅推特场景）...")
            sys.stdout.flush()
            result = ask_xai(
                prompt=prompt,
                system=args.system,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        ds_model = _load_env("DEEPSEEK_MODEL") or "deepseek-v4-flash"
        print(f"🤖 调用 DeepSeek ({ds_model}) ...")
        sys.stdout.flush()
        content = ask_deepseek(
            prompt=prompt,
            system=args.system,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )

    if args.save:
        Path(args.save).write_text(content, encoding="utf-8")
        print(f"✅ 已保存到 {args.save}")
    else:
        print(content)


if __name__ == "__main__":
    main()
