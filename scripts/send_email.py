#!/usr/bin/env python3
"""
股市日报邮件发送脚本

支持三种发送方式：
  1. Microsoft Graph API + OAuth2 设备码流程（推荐，支持 Outlook.com / Office 365）
  2. Exchange SMTP + OAuth2（需要应用注册）
  3. Outlook COM 自动化（仅 Windows，需要安装经典版 Outlook）
"""

import os
import sys
import json
import argparse
import smtplib
import time
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

# 修复 Windows 下 GBK 编码导致的 emoji/中文输出问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 配置
# ============================================================

# Microsoft Graph API 权限范围
GRAPH_SCOPES = ["https://graph.microsoft.com/Mail.Send"]

# Microsoft 官方客户端 ID（适用于个人 Microsoft 账户和设备码流程）
# 这是 Azure CLI 的公共客户端 ID，支持 device_code 流程
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Microsoft Azure PowerShell
# 备选：d3590ed6-52b3-4102-aeff-aad2292ab01c (Microsoft Office)

AUTHORITY = "https://login.microsoftonline.com/common"

TOKEN_CACHE_FILE = Path(__file__).parent.parent / ".token_cache.json"


def load_config():
    """加载项目配置文件"""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """保存配置文件"""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_token_cache():
    """加载缓存的 token"""
    if TOKEN_CACHE_FILE.exists():
        with open(TOKEN_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_token_cache(cache):
    """保存 token 缓存"""
    with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# ============================================================
# Microsoft Graph API 发送（推荐方式）
# ============================================================

def acquire_token_device_code(config):
    """
    使用设备码流程获取 OAuth2 token。
    用户需要在浏览器中打开 https://microsoft.com/devicelogin 并输入设备码。
    """
    import msal

    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

    # 查看是否有缓存的账号
    cache = load_token_cache()
    accounts = app.get_accounts()

    if accounts:
        # 尝试静默获取 token
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
        if result:
            print(f"✅ 使用缓存的 token 登录 → {accounts[0].get('username', 'unknown')}")
            return result

    # 如果没有缓存，启动设备码流程
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if "user_code" not in flow:
        print(f"❌ 设备码流程启动失败：{flow.get('error_description', flow)}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  🔐 首次使用需要登录 Microsoft 账户")
    print("=" * 60)
    print(f"\n  📋 设备码：{flow['user_code']}")
    print(f"  🌐 请在浏览器中打开：{flow['verification_uri']}")
    print(f"\n  等待登录中...")

    # 用设备码轮询获取 token
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        print(f"✅ 登录成功！\n")
        return result
    else:
        print(f"❌ 登录失败：{result.get('error_description', result)}")
        sys.exit(1)


def send_via_smtp_password(config, subject, html_body):
    """通过 SMTP + 账号密码/授权码发送邮件（适用于 QQ/163/126 等国内邮箱）"""
    import smtplib

    email_user = config["email"]["sender_email"]
    email_pass = os.environ.get("MYSTOCK_EMAIL_PASS") or config["email"].get("password", "")

    if not email_pass:
        print("❌ 错误：未设置邮箱密码/授权码")
        print("   请通过环境变量设置：")
        print('   $env:MYSTOCK_EMAIL_PASS = "your-auth-code"')
        print("   或者在 config.json 中添加 password 字段")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["From"] = email_user
    msg["To"] = config["email"]["recipient_email"]
    msg["Subject"] = subject

    text_body = re.sub(r"<[^>]+>", "", html_body)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(config["email"]["smtp_server"], config["email"]["smtp_port"])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        print(f"✅ 邮件已通过 SMTP 发送成功 → {config['email']['recipient_email']}")
        print(f"   发件人：{email_user}")
        print(f"   服务器：{config['email']['smtp_server']}:{config['email']['smtp_port']}")
    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP 认证失败，请检查授权码是否正确")
        print("   QQ 邮箱：登录网页版 → 设置 → 账户 → POP3/SMTP 服务 → 生成授权码")
        sys.exit(1)
    except Exception as e:
        print(f"❌ SMTP 发送失败：{e}")
        sys.exit(1)


def send_via_graph_api(config, subject, html_body):
    """通过 Microsoft Graph API 发送邮件（支持 Outlook.com 和 Office 365）"""
    import requests

    token_result = acquire_token_device_code(config)
    access_token = token_result["access_token"]

    # 构造邮件
    email_data = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": config["email"]["recipient_email"]
                    }
                }
            ],
        },
        "saveToSentItems": "true",
    }

    # 调用 Graph API
    endpoint = "https://graph.microsoft.com/v1.0/me/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(endpoint, headers=headers, json=email_data)

    if response.status_code == 202:
        print(f"✅ 邮件已通过 Microsoft Graph API 发送成功")
        print(f"   发件人：{config['email']['sender_email']}")
        print(f"   收件人：{config['email']['recipient_email']}")
    elif response.status_code == 401:
        print("❌ Token 已过期，正在尝试重新登录...")
        # 清除缓存，重试
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()
        # 递归重试一次
        return send_via_graph_api(config, subject, html_body)
    else:
        error_info = response.json() if response.text else "无详细信息"
        print(f"❌ Graph API 发送失败 [{response.status_code}]：{error_info}")
        sys.exit(1)


# ============================================================
# SMTP + OAuth2 发送（XOAUTH2）
# ============================================================

def send_via_smtp_oauth2(config, subject, html_body):
    """通过 SMTP + XOAUTH2 认证发送邮件"""
    token_result = acquire_token_device_code(config)
    access_token = token_result["access_token"]
    email_user = config["email"]["sender_email"]

    msg = MIMEMultipart("alternative")
    msg["From"] = email_user
    msg["To"] = config["email"]["recipient_email"]
    msg["Subject"] = subject

    text_body = re.sub(r"<[^>]+>", "", html_body)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # XOAUTH2 认证字符串
    auth_string = f"user={email_user}\x01auth=Bearer {access_token}\x01\x01"

    try:
        server = smtplib.SMTP(config["email"]["smtp_server"], config["email"]["smtp_port"])
        server.starttls()
        server.ehlo()
        server.auth("XOAUTH2", lambda: auth_string)
        server.send_message(msg)
        server.quit()
        print(f"✅ 邮件已通过 SMTP OAuth2 发送成功 → {config['email']['recipient_email']}")
    except Exception as e:
        print(f"❌ SMTP OAuth2 发送失败：{e}")
        # 降级到 Graph API
        print("   尝试降级到 Graph API 方式...")
        send_via_graph_api(config, subject, html_body)


# ============================================================
# Outlook COM 自动化（Windows 经典版 Outlook）
# ============================================================

def send_via_outlook_com(config, subject, html_body):
    """通过 Outlook COM 自动化发送邮件（需要安装经典版 Outlook）"""
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.Subject = subject
        mail.HTMLBody = html_body
        mail.To = config["email"]["recipient_email"]
        mail.Send()
        print(f"✅ 邮件已通过 Outlook COM 发送成功 → {config['email']['recipient_email']}")
    except ImportError:
        print("❌ 缺少 pywin32 库，请运行：pip install pywin32")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Outlook COM 发送失败：{e}")
        print("   请确保 Outlook 经典版已安装并登录")
        sys.exit(1)


# ============================================================
# Markdown → HTML 转换
# ============================================================

def markdown_to_html(md_content: str) -> str:
    """将 Markdown 报告转换为 HTML 格式的邮件正文"""
    lines = md_content.split("\n")
    html_lines = ['<html><body style="font-family: \'Microsoft YaHei\', \'Segoe UI\', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.8;">']
    in_list = False
    in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped == "---":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("<hr>")
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h1 style="color: #1a1a1a; border-bottom: 3px solid #d32f2f; padding-bottom: 10px;">{stripped[2:]}</h1>')
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h2 style="color: #d32f2f; margin-top: 25px;">{stripped[3:]}</h2>')
        elif stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<h3 style="color: #444; margin-top: 20px;">{stripped[4:]}</h3>')
        elif stripped.startswith("#### "):
            html_lines.append(f'<h4 style="color: #555; margin-top: 15px;">{stripped[5:]}</h4>')

        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append('<ul style="line-height: 1.8; padding-left: 20px;">')
                in_list = True
            html_lines.append(f"<li>{stripped[2:]}</li>")

        elif stripped.startswith("> "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<blockquote style="border-left: 4px solid #d32f2f; margin: 10px 0; padding: 10px 15px; background: #fff3e0; color: #666; border-radius: 0 4px 4px 0;">{stripped[2:]}</blockquote>')

        elif stripped.startswith("|"):
            if not in_table:
                html_lines.append('<table style="border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 14px;">')
                in_table = True
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(c.replace("-", "").replace(":", "").strip() == "" for c in cells):
                continue
            is_header = all(c.startswith("**") for c in cells if c)
            tag = "th" if is_header else "td"
            clean_cells = [c.replace("**", "") for c in cells]
            html_lines.append("<tr>")
            for cell in clean_cells:
                if tag == "th":
                    style = 'style="border: 1px solid #ddd; padding: 8px 12px; text-align: left; background: #f5f5f5; font-weight: bold;"'
                else:
                    style = 'style="border: 1px solid #ddd; padding: 8px 12px;"'
                html_lines.append(f"<{tag} {style}>{cell}</{tag}>")
            html_lines.append("</tr>")

        elif stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            # 处理行内格式
            text = stripped
            text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
            html_lines.append(f"<p style='margin: 6px 0;'>{text}</p>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append("<br>")

    if in_list:
        html_lines.append("</ul>")
    if in_table:
        html_lines.append("</table>")

    html_lines.append("</body></html>")
    return "\n".join(html_lines)


# ============================================================
# 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="📧 股市日报邮件发送工具")
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--file", help="报告文件路径（Markdown 格式）")
    parser.add_argument("--body", help="直接传入 HTML 正文（--file 的替代方案）")
    parser.add_argument("--method", choices=["graph", "smtp", "outlook"],
                        help="发送方式（默认按 config.json 配置）")
    parser.add_argument("--setup", action="store_true",
                        help="首次设置：进行 OAuth2 设备码登录并缓存 token")
    args = parser.parse_args()

    config = load_config()

    # 获取邮件正文
    if args.file:
        report_path = Path(args.file)
        if not report_path.exists():
            print(f"❌ 错误：报告文件不存在：{args.file}")
            sys.exit(1)
        body_md = report_path.read_text(encoding="utf-8")
        body_html = markdown_to_html(body_md)
    elif args.body:
        body_html = args.body
    else:
        print("❌ 错误：请提供 --file 或 --body 参数")
        sys.exit(1)

    # 确定发送方式
    method = args.method or config["email"].get("method", "graph")

    if method == "graph":
        send_via_graph_api(config, args.subject, body_html)
    elif method == "smtp":
        send_via_smtp_oauth2(config, args.subject, body_html)
    elif method == "smtp_password":
        send_via_smtp_password(config, args.subject, body_html)
    elif method == "outlook":
        send_via_outlook_com(config, args.subject, body_html)
    else:
        print(f"❌ 未知的发送方式：{method}")
        print("   支持：graph, smtp, smtp_password, outlook")
        sys.exit(1)


if __name__ == "__main__":
    main()
