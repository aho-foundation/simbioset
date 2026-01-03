"""
API routes for bot management.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request

from api.bot.tg import BotManager


router = APIRouter(prefix="/api/bot", tags=["bot"])

# Global bot manager instance
# This should be managed by dependency injection, but for now we'll use this approach
_bot_manager: Optional[BotManager] = None


def get_bot_manager() -> BotManager:
    """Get bot manager instance."""
    if _bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    return _bot_manager


def set_bot_manager(manager: BotManager) -> None:
    """Set bot manager instance."""
    global _bot_manager
    _bot_manager = manager


# Webhook handler for Telegram bot
@router.post("/")
async def handle_webhook_update(request: Request, manager: BotManager = Depends(get_bot_manager)):
    """
    Handle incoming webhook updates from Telegram.
    """
    try:
        if manager.bot is None:
            raise HTTPException(status_code=503, detail="Bot instance not available")

        update_data = await request.json()
        update = manager.bot.handle_webhook_update(update_data)

        # Process the single update
        await manager.processor._process_single_update(manager.bot, update)

        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")
