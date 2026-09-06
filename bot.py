import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import handlers as h
from config import load_config
from db import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    app.bot_data["db"] = await Database.connect(app.bot_data["cfg"].database_url)
    app.job_queue.run_repeating(expire_premium, interval=3600, first=10)
    logger.info("Database connected")


async def expire_premium(context) -> None:
    await context.bot_data["db"].expire_stale_premium()


def main() -> None:
    cfg = load_config()
    app = Application.builder().token(cfg.bot_token).post_init(post_init).build()
    app.bot_data["cfg"] = cfg

    app.add_handler(CommandHandler("start", h.start))
    app.add_handler(CallbackQueryHandler(h.on_terms_accept, pattern="^terms_accept$"))
    app.add_handler(CallbackQueryHandler(h.on_gender, pattern="^gender_"))
    app.add_handler(CallbackQueryHandler(h.on_looking_for, pattern="^look_"))
    app.add_handler(CallbackQueryHandler(h.on_find_partner, pattern="^find_partner$"))
    app.add_handler(CallbackQueryHandler(h.on_cancel_search, pattern="^cancel_search$"))
    app.add_handler(CallbackQueryHandler(h.on_skip, pattern="^skip$"))
    app.add_handler(CallbackQueryHandler(h.on_end_chat, pattern="^end_chat$"))
    app.add_handler(CallbackQueryHandler(h.on_report, pattern="^report$"))
    app.add_handler(CallbackQueryHandler(h.on_block, pattern="^block$"))
    app.add_handler(CallbackQueryHandler(h.on_keep_waiting, pattern="^keep_waiting$"))
    app.add_handler(CallbackQueryHandler(h.on_ai_offer, pattern="^ai_offer$"))
    app.add_handler(CallbackQueryHandler(h.on_ai_pick, pattern="^ai_pick_"))
    app.add_handler(CallbackQueryHandler(h.on_ai_end_to_search, pattern="^ai_end_to_search$"))
    app.add_handler(CallbackQueryHandler(h.on_ai_end, pattern="^ai_end$"))
    app.add_handler(CallbackQueryHandler(h.on_premium_menu, pattern="^premium_menu$"))
    app.add_handler(CallbackQueryHandler(h.on_buy_plan, pattern="^buy_"))
    app.add_handler(PreCheckoutQueryHandler(h.on_precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, h.on_successful_payment))
    app.add_handler(CommandHandler("paysupport", h.paysupport))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, h.forward_message))
    app.add_error_handler(h.on_error)

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
