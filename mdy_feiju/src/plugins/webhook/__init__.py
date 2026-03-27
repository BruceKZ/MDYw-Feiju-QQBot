import os
import logging

import nonebot
from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

__plugin_meta__ = PluginMetadata(
    name="Webhook Notifier",
    description="Receives HTTP webhook calls and forwards them as QQ private messages.",
    usage="POST /webhook/experiment with plain text body and optional Bearer token.",
)

# ── Configuration ──────────────────────────────────────────────

WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")
# Default target for notifications: first SUPERUSER
_superusers: set[str] = get_driver().config.superusers
DEFAULT_TARGET_QQ: str = next(iter(_superusers)) if _superusers else ""


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

        # ── Read plain text body ──
        text = (await request.body()).decode("utf-8").strip()
        if not text:
            return JSONResponse({"ok": False, "error": "Empty body"}, status_code=400)

        # ── Resolve target QQ (via query param or default) ──
        target_qq = (request.query_params.get("target_qq", "") or DEFAULT_TARGET_QQ).strip()
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

        try:
            await bot.send_private_msg(user_id=int(target_qq), message=text)
        except Exception as e:
            logger.exception("Failed to send webhook notification to %s", target_qq)
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

        logger.info("Webhook notification sent to %s", target_qq)
        return JSONResponse({"ok": True})

    logger.info("Webhook routes registered at /webhook/experiment")
