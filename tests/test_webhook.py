#!/usr/bin/env python3
"""
Test script to verify that the Telegram bot webhook server starts correctly.
"""

import asyncio
import os
import signal
import sys


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"\nReceived signal {num}, shutting down...")
    sys.exit(0)


async def run_test():
    """Run the webhook server test."""
    print("Starting Telegram bot webhook server test...")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set environment variable to ensure webhook mode is used
    os.environ["DOKKU_PROXY_PORT"] = "80"  # This will trigger webhook mode in the main script

    # Set a dummy bot token to bypass the environment variable check
    os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:dummy_bot_token_for_testing"

    try:
        # Import here to avoid issues before environment is set up
        from api.bot.main import start_bot

        # Start the bot - this should now start the webhook server
        await start_bot()
        print("Bot started successfully!")
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_test())
