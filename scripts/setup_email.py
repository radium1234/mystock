#!/usr/bin/env python3
"""
mystock 邮箱设置向导
首次使用前运行一次，通过浏览器登录 Outlook 账户，授权后自动缓存 token。
后续发送邮件无需再次登录。
"""

import sys
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_DIR = Path(__file__).parent.parent
TOKEN_CACHE = PROJECT_DIR / ".token_cache.json"

# Microsoft 官方客户端 ID（适用于个人 Microsoft 账户）
# 使用 Microsoft Azure CLI 的公共客户端 ID
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["https://graph.microsoft.com/Mail.Send"]


def main():
    import msal

    print("\n" + "=" * 60)
    print("  📧 mystock 邮箱设置向导")
    print("=" * 60)
    print("\n  发件邮箱：berserker.lee@outlook.com")
    print("  收件邮箱：berserker.lee@outlook.com")
    print()

    # 检查是否有缓存的 token
    if TOKEN_CACHE.exists():
        with open(TOKEN_CACHE, encoding="utf-8") as f:
            cache_data = json.load(f)
        if cache_data:
            print("  ℹ️  已有缓存的 token，先尝试刷新...")
            app = msal.PublicClientApplication(
                CLIENT_ID, authority=AUTHORITY,
                token_cache=msal.SerializableTokenCache()
            )
            app.token_cache.deserialize(json.dumps(cache_data))
            accounts = app.get_accounts()
            if accounts:
                result = app.acquire_token_silent(SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    # 保存更新后的缓存
                    if app.token_cache.has_state_changed:
                        TOKEN_CACHE.write_text(
                            app.token_cache.serialize(), encoding="utf-8"
                        )
                    print("  ✅ Token 仍然有效，无需重新登录！")
                    print(f"     账户：{accounts[0].get('username', 'unknown')}")
                    print()
                    return
            print("  ⚠️  Token 已过期，需要重新登录。\n")

    # 设备码流程
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"❌ 启动设备码流程失败：{flow.get('error_description', flow)}")
        sys.exit(1)

    print("=" * 60)
    print("  🔐 请按以下步骤完成登录授权：")
    print("=" * 60)
    print()
    print(f"  📋 设备码：{flow['user_code']}")
    print()
    print(f"  🌐 请在浏览器中打开：")
    print(f"     {flow['verification_uri']}")
    print()
    print(f"  1. 输入上面的设备码")
    print(f"  2. 使用 berserker.lee@outlook.com 登录")
    print(f"  3. 授权「发送邮件」权限")
    print()
    print("  ⏳ 等待登录完成...")
    print()

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        # 保存 token 缓存
        cache_json = app.token_cache.serialize()
        TOKEN_CACHE.write_text(cache_json, encoding="utf-8")
        print("\n" + "=" * 60)
        print("  ✅ 登录成功！Token 已缓存。")
        print("=" * 60)
        print()
        print("  现在可以运行以下命令发送测试邮件：")
        print("  python scripts/send_email.py --subject \"测试\" --body \"<h1>测试</h1>\"")
        print()
    else:
        error = result.get("error_description", str(result))
        print(f"\n❌ 登录失败：{error}")
        print("   请重新运行此脚本。")
        sys.exit(1)


if __name__ == "__main__":
    main()
