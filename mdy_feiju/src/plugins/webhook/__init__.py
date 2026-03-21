import os
import json
import logging
from datetime import datetime, timezone, timedelta

import nonebot
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

__plugin_meta__ = PluginMetadata(
    name="Webhook Notifier",
    description="Receives HTTP webhook calls and forwards them as QQ private messages.",
    usage="POST /webhook/experiment with JSON body and Bearer token.",
)

# ── Configuration ──────────────────────────────────────────────

WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")
# Default target for notifications: first SUPERUSER
_superusers: set[str] = get_driver().config.superusers
DEFAULT_TARGET_QQ: str = next(iter(_superusers)) if _superusers else ""

# ── Status emoji mapping ──────────────────────────────────────

_STATUS_EMOJI = {
    "success": "✅",
    "failed": "❌",
    "error": "❌",
    "running": "🔄",
    "timeout": "⏰",
}


def _format_message(data: dict) -> str:
    """Format the webhook JSON into a readable QQ message."""
    title = data.get("title", "Unknown Experiment")
    status = data.get("status", "unknown")
    message = data.get("message", "")

    emoji = _STATUS_EMOJI.get(status.lower(), "📋")
    now_shanghai = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"📊 实验通知",
        f"━━━━━━━━━━━━━━",
        f"📌 {title}",
        f"{emoji} {status}",
        f"🕐 {now_shanghai}",
        f"━━━━━━━━━━━━━━",
    ]
    if message:
        lines.append(message)

    return "\n".join(lines)


# ── Register FastAPI route on startup ─────────────────────────

@get_driver().on_startup
async def _register_routes():
    app: FastAPI = nonebot.get_app()  # type: ignore

    @app.post("/webhook/experiment")
    async def webhook_experiment(request: Request):
        # ── Auth check ──
        if WEBHOOK_SECRET:
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {WEBHOOK_SECRET}":
                return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

        # ── Parse body ──
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

        if not isinstance(data, dict):
            return JSONResponse({"ok": False, "error": "Body must be a JSON object"}, status_code=400)

        # ── Resolve target QQ ──
        target_qq = str(data.get("target_qq", "")).strip() or DEFAULT_TARGET_QQ
        if not target_qq:
            return JSONResponse(
                {"ok": False, "error": "No target_qq and no SUPERUSERS configured"},
                status_code=400,
            )

        # ── Get bot and send ──
        try:
            bot = nonebot.get_bot()
        except ValueError:
            return JSONResponse(
                {"ok": False, "error": "Bot not connected yet, try again later"},
                status_code=503,
            )

        text = _format_message(data)
        try:
            await bot.send_private_msg(user_id=int(target_qq), message=text)
        except Exception as e:
            logger.exception("Failed to send webhook notification to %s", target_qq)
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

        logger.info("Webhook notification sent to %s: %s", target_qq, data.get("title", ""))
        return JSONResponse({"ok": True})

    logger.info("Webhook routes registered at /webhook/experiment")
