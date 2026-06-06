#!/usr/bin/env python3
"""
mystock API 助手 — 通过 OpenRouter 调用 AI 模型

用法：
  python scripts/grok_api.py "你的问题"           # 默认 DeepSeek
  python scripts/grok_api.py --model grok "..."   # 用 Grok 推特搜索
  python scripts/grok_api.py --tweet "搜索推文"    # 快捷推特搜索

模型策略：
  - 推特/X 数据 → Grok 4.20（有 X 集成）
  - 其他所有任务 → DeepSeek Chat（便宜好用）

环境变量：
  OPENROUTER_API_KEY — OpenRouter API key
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

# 模型配置
DEFAULT_MODEL = "deepseek/deepseek-chat"         # 默认：DeepSeek（便宜）
TWITTER_MODEL = "x-ai/grok-4.20"                 # 推特：Grok 4.20（有X集成）

MODELS = {
    "deepseek": "deepseek/deepseek-chat",        # ~$0.14 / $0.28 per M tokens
    "grok": "x-ai/grok-4.20",                    # ~$0.00125 / $0.0025
    "grok-build": "x-ai/grok-build-0.1",         # ~$0.001 / $0.002 最便宜
    "grok-4.3": "x-ai/grok-4.3",                 # ~$0.00125 / $0.0025
    "qwen": "qwen/qwen-2.5-72b-instruct",        # ~$0.35 / $0.40 国产替补
}


def load_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    print("❌ 未设置 OPENROUTER_API_KEY")
    print("   请在 .env 文件中添加：")
    print('   OPENROUTER_API_KEY="sk-or-v1-..."')
    sys.exit(1)


def ask(model, prompt, system=None, max_tokens=4000, temperature=0.7, tools=None, tool_choice="auto"):
    """调用任意模型 via OpenRouter"""
    api_key = load_api_key()
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
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mystock",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        raise Exception(err.get("error", {}).get("message", str(e)))


def ask_xai(model, prompt, system=None, max_tokens=4000, temperature=0.7, tools=None, tool_choice="auto"):
    """调用 xAI 官方 API（通过 Clash 代理）"""
    api_key = os.environ.get("XAI_API_KEY") or ""
    if not api_key:
        # 从 .env 读取
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("XAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
    if not api_key:
        raise Exception("未设置 XAI_API_KEY")

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
        "https://api.x.ai/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        return result
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        raise Exception(err.get("error", {}).get("message", str(e)))


def search_twitter_api(query, max_results=10):
    """通过 Twitter API v2 搜索推文"""
    bearer = os.environ.get("TWITTER_BEARER_TOKEN") or ""
    if not bearer:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("TWITTER_BEARER_TOKEN="):
                    bearer = line.split("=", 1)[1].strip()
    if not bearer:
        raise Exception("未设置 TWITTER_BEARER_TOKEN")

    import urllib.parse
    url = f"https://api.twitter.com/2/tweets/search/recent?query={urllib.parse.quote(query)}&max_results={max_results}&tweet.fields=created_at,public_metrics,author_id&expansions=author_id&user.fields=username,name"

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


def ask_twitter_grok(prompt, max_tokens=4000):
    """用 Grok (xAI API) + x_search 工具 → X API 搜索 → Grok 分析"""
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

    system = "你是推特分析师。先用 x_search 工具搜索推文，然后基于搜索结果给出详细分析报告。用中文回答。"

    # Step 1: 让 Grok 生成搜索词
    result = ask_xai(
        model="grok-4.3",
        system=system,
        prompt=prompt,
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
        # 返回错误给 Grok
        error_result = json.dumps({"error": str(e)})
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
            msg,
            {"role": "tool", "tool_call_id": tc["id"], "content": error_result}
        ]
        result2 = ask_xai(model="grok-4.3", prompt="", max_tokens=max_tokens, tools=[])
        # 重新构造请求
        body = {"model": "grok-4.3", "messages": messages, "max_tokens": max_tokens}
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions", data=data,
            headers={"Content-Type": "application/json; charset=utf-8",
                     "Authorization": "Bearer " + (os.environ.get("XAI_API_KEY") or "")}
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result2 = json.loads(resp.read())
        return result2.get("choices", [{}])[0].get("message", {}).get("content", "")

    print(f"  ✅ 找到 {len(tweets)} 条推文")
    sys.stdout.flush()

    # Step 4: 返回搜索结果给 Grok 分析
    tweets_json = json.dumps({"tweets": tweets}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        msg,
        {"role": "tool", "tool_call_id": tc["id"], "content": tweets_json}
    ]

    body = {"model": "grok-4.3", "messages": messages, "max_tokens": max_tokens}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions", data=data,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": "Bearer " + (os.environ.get("XAI_API_KEY") or "")}
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result2 = json.loads(resp.read())
    return result2.get("choices", [{}])[0].get("message", {}).get("content", "")
    tool_calls = msg.get("tool_calls")

    if tool_calls:
        print(f"\n🔍 Grok 发起搜索: {tool_calls[0]['function']['arguments']}")
        print("⚠️  需要 X API 密钥才能执行实时搜索。")
        print("   返回的是 Grok 的原始回复。\n")

    return msg.get("content") or "（模型正在搜索，请稍后重试）"


def ask_twitter(prompt, max_tokens=4000):
    """用 Grok 搜索/分析推特内容（兼容旧接口）"""
    system = "你是推特分析师。请基于已有知识分析推特内容。用中文回答。"
    return ask(TWITTER_MODEL, prompt, system=system, max_tokens=max_tokens)


def ask_deepseek(prompt, system=None, max_tokens=4000):
    """用 DeepSeek 做通用分析"""
    return ask(DEFAULT_MODEL, prompt, system=system, max_tokens=max_tokens)


def main():
    import argparse

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="🤖 mystock API 助手")
    parser.add_argument("prompt", nargs="?", help="输入问题")
    parser.add_argument("--model", "-m", default="deepseek",
                        choices=list(MODELS.keys()),
                        help="模型（默认: deepseek, 推特用: grok）")
    parser.add_argument("--tweet", "-t", action="store_true",
                        help="快捷推特搜索模式（自动用 Grok）")
    parser.add_argument("--xai", action="store_true",
                        help="使用 xAI 官方 API（需代理）")
    parser.add_argument("--search", "-s", action="store_true",
                        help="启用 x_search 工具搜索 X/Twitter（需 xAI API）")
    parser.add_argument("--system", help="系统提示词")
    parser.add_argument("--file", "-f", help="从文件读取输入")
    parser.add_argument("--save", help="输出保存到文件")
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")

    args = parser.parse_args()

    if args.list_models:
        print("\n📋 可用模型：")
        for k, v in MODELS.items():
            print(f"  {k:<12} → {v}")
        print("\n💡 默认用 deepseek（便宜），推特用 grok（有 X 集成）")
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
    if args.xai or args.search:
        # 使用 xAI 官方 API
        if args.search:
            print("🤖 调用 xAI Grok + x_search 工具 ...")
            sys.stdout.flush()
            content = ask_twitter_grok(prompt, max_tokens=args.max_tokens)
        else:
            print("🤖 调用 xAI Grok ...")
            sys.stdout.flush()
            result = ask_xai(
                model="grok-4.20-0309-non-reasoning",
                system=args.system,
                prompt=prompt,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    elif args.tweet:
        model_name = "Grok 4.20 (推特模式)"
        print(f"🤖 调用 {model_name} ...")
        sys.stdout.flush()
        content = ask(model=TWITTER_MODEL, prompt=prompt, system=args.system,
                      max_tokens=args.max_tokens, temperature=args.temperature)
    else:
        model_name = args.model
        model = MODELS.get(args.model, args.model)
        print(f"🤖 调用 {model_name} ...")
        sys.stdout.flush()
        content = ask(model=model, prompt=prompt, system=args.system,
                      max_tokens=args.max_tokens, temperature=args.temperature)

    if args.save:
        Path(args.save).write_text(content, encoding="utf-8")
        print(f"✅ 已保存到 {args.save}")
    else:
        print(content)


if __name__ == "__main__":
    main()
