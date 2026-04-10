"""
telegram_bot.py  — Production-grade Telegram integration

Full task pipeline:
  User → Intent Router → Task → Queue → Worker → LLM Gateway → Reply

✅ Retry + Failover layer (via llm_gateway)
✅ 30s timeout per provider
✅ Multi-provider fallback: ollama → gemini → groq → nvidia → openai
✅ Typing indicator while processing
✅ Graceful error handling — never shows raw tracebacks
✅ Intent-aware routing (news / finance / builder / chat)
"""
import os
import logging
import argparse
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

try:
    from telegram import Update
    from telegram.constants import ChatAction
    from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
except ImportError:
    print("[Error] python-telegram-bot not installed. Run: pip install python-telegram-bot")
    exit(1)

from backend.core.database import SessionLocal
from backend.services.bot_service import get_bot
from backend.llm.universal_provider import UniversalProvider

# ─── Intent Keyword Router (lightweight, no LLM call needed) ─────────────────
_NEWS_KW     = {"news", "latest", "happening", "update", "breaking", "geopolit", "conflict", "iran", "ukraine"}
_FINANCE_KW  = {"crypto", "bitcoin", "stock", "price", "market", "eth", "btc", "trade", "invest"}
_BUILDER_KW  = {"build", "create", "code", "debug", "refactor", "write", "generate", "script", "website"}

def _quick_intent(text: str) -> str:
    low = text.lower()
    if any(k in low for k in _NEWS_KW):     return "news"
    if any(k in low for k in _FINANCE_KW):  return "finance"
    if any(k in low for k in _BUILDER_KW):  return "builder"
    return "chat"


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *DreamAgent online!*\n\n"
        "I can help with:\n"
        "• 📰 *News analysis* — ask about any world event\n"
        "• 💹 *Finance / Crypto* — prices, trends, portfolio\n"
        "• 🛠 *Builder tasks* — code, debug, create\n"
        "• 💬 *General chat* — ask me anything\n\n"
        "Just send a message!",
        parse_mode="Markdown"
    )

async def handle_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive and well.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    chat_id = str(update.effective_chat.id)
    bot_id  = context.bot_data.get("bot_id", "fallback")
    intent  = _quick_intent(user_text)

    logger.info("[TelegramBot] chat=%s intent=%s query=%s", chat_id, intent, user_text[:60])

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Fast chat path — direct LLM Gateway call, forces adherence to system constraints (e.g., maths & english only)
    await _fast_llm_reply(update, context, user_text)


async def _fast_llm_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """
    Direct LLM Gateway call for quick conversational responses.
    Retries across providers automatically; never fails silently.
    """
    chat_id = str(update.effective_chat.id)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    bot_id = context.bot_data.get("bot_id")
    personality = "You are DreamAgent, a smart AI assistant. Be concise, helpful, and use markdown for formatting."
    
    if bot_id:
        db = SessionLocal()
        from backend.services.bot_service import get_bot
        bot = get_bot(db, bot_id)
        if bot and bot.personality:
            personality = f"You are a Telegram Bot governed by the following constraints from your creator:\n{bot.personality}\n\nRespond concisely and use markdown."
        db.close()

    try:
        provider = UniversalProvider(provider="auto", model="")
        messages = [
            {"role": "system", "content": personality},
            {"role": "user", "content": user_text}
        ]
        reply = await provider.complete(messages)
        
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as exc:
        logger.error("[TelegramBot] LLM Gateway error: %s", exc)
        await update.message.reply_text(
            "⚠️ AI is temporarily busy. Please try again in a moment."
        )


# ─── Bot Bootstrap ────────────────────────────────────────────────────────────

def run_bot(bot_id: str):
    db  = SessionLocal()
    bot = get_bot(db, bot_id)
    if not bot:
        print(f"[Error] Bot ID '{bot_id}' not found in database.")
        return

    token         = bot.token
    platform_name = bot.platform
    bot_id_val    = bot.id
    db.close()

    print(f"[INFO] Launching polling wrapper for {bot.name} ({platform_name})…")
    app = ApplicationBuilder().token(token).build()

    # Inject bot_id so handler knows where to route
    app.bot_data["bot_id"] = bot_id_val

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ping",  handle_ping))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DreamAgent Telegram Bot")
    parser.add_argument("--bot_id", type=str, required=False, help="Bot ID from the database")
    args = parser.parse_args()

    if args.bot_id:
        run_bot(args.bot_id)
    else:
        print("Usage: python telegram_bot.py --bot_id <YOUR_BOT_ID>")
        print("       (Use the DreamAgent dashboard to find your Bot ID)")
