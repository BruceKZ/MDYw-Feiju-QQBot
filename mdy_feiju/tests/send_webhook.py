#!/usr/bin/env python3
"""
Webhook 客户端 —— 在实验机器上使用
===================================

用法:
    python send_webhook.py --url <WEBHOOK_URL> --secret <TOKEN> \\
        --title "ResNet50" --status success --message "Acc=96.2%"

通过 Cloudflare Tunnel 暴露的固定地址:
    https://api.bruce12138.com/webhook/experiment

完整示例:
    python send_webhook.py \\
        --url https://api.bruce12138.com/webhook/experiment \\
        --secret my_secret_token \\
        --title "BERT Fine-tune Epoch 10" \\
        --status success \\
        --message "Val F1: 0.923, Loss: 0.041"

也可以导入为模块在训练脚本里直接调用:

    from send_webhook import notify
    notify(
        url="https://api.bruce12138.com/webhook/experiment",
        secret="my_secret_token",
        title="BERT Fine-tune",
        status="success",
        message="Val F1: 0.923",
    )
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    print("需要 requests 库: pip install requests")
    sys.exit(1)


def notify(
    url: str,
    secret: str,
    title: str,
    status: str = "success",
    message: str = "",
    target_qq: str = "",
) -> dict:
    """Send a webhook notification and return the response JSON."""
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    payload = {"title": title, "status": status, "message": message}
    if target_qq:
        payload["target_qq"] = target_qq

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    print(f"Status: {resp.status_code}")
    try:
        result = resp.json()
    except Exception:
        result = {"raw": resp.text}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description="Send experiment webhook notification to QQ bot")
    parser.add_argument("--url", required=True, help="Full webhook URL, e.g. http://localhost:8080/webhook/experiment")
    parser.add_argument("--secret", default="", help="Bearer token (WEBHOOK_SECRET)")
    parser.add_argument("--title", required=True, help="Experiment title")
    parser.add_argument("--status", default="success", choices=["success", "failed", "error", "running", "timeout"])
    parser.add_argument("--message", default="", help="Extra details (metrics, etc.)")
    parser.add_argument("--target-qq", default="", help="Target QQ user ID (defaults to first SUPERUSER)")
    args = parser.parse_args()

    notify(
        url=args.url,
        secret=args.secret,
        title=args.title,
        status=args.status,
        message=args.message,
        target_qq=args.target_qq,
    )


if __name__ == "__main__":
    main()
