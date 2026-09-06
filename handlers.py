import logging
from datetime import datetime, timezone

from telegram import LabeledPrice, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import companion
import keyboards as kb
import payments
from db import Database

SEARCH_TIMEOUT_SECONDS = 45

logger = logging.getLogger(__name__)

TERMS_TEXT = (
    "Welcome to AnonymousChatXBot 🎭\n\n"
    "You'll be matched anonymously with a stranger. Never share personal info. "
    "Be respectful — abuse gets you banned.\n\nDo you accept?"
)
HOME_TEXT = "🏠 Home Menu\n\nTap below to find a chat partner."


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.bot_data["db"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db(context)
    user = await db.get_or_create_user(update.effective_chat.id)
    if user["accepted_terms"]:
        await show_home(update.effective_chat.id, context)
    else:
        await update.message.reply_text(TERMS_TEXT, reply_markup=kb.terms_kb())


async def on_terms_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await get_db(context).set_field(q.message.chat_id, accepted_terms=True)
    await q.edit_message_text("Select your gender:", reply_markup=kb.gender_kb())


async def on_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await get_db(context).set_field(q.message.chat_id, gender=q.data.split("_")[1])
    await q.edit_message_text("Who are you looking for?", reply_markup=kb.looking_for_kb())


async def on_looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await get_db(context).set_field(q.message.chat_id, looking_for=q.data.split("_")[1])
    await q.delete_message()
    await show_home(q.message.chat_id, context)


async def show_home(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id, HOME_TEXT, reply_markup=kb.home_kb())


async def notify_matched(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id, "✅ Partner found! Say hi 👋", reply_markup=kb.chat_kb())


async def start_search(chat_id: int, context: ContextTypes.DEFAULT_TYPE, edit=None):
    db = get_db(context)
    user = await db.get_or_create_user(chat_id)
    if not user["is_premium"] and user["free_matches"] <= 0:
        text = "🔒 You've used all 15 free matches. Upgrade to Premium for unlimited chats."
        await (edit(text) if edit else context.bot.send_message(chat_id, text))
        return

    await db.set_field(chat_id, status="searching")
    text = "🔍 Searching for a partner..."
    if edit:
        await edit(text, reply_markup=kb.searching_kb())
    else:
        await context.bot.send_message(chat_id, text, reply_markup=kb.searching_kb())

    partner_id = await db.find_and_make_match(chat_id)
    if partner_id:
        await db.decrement_free_match(chat_id)
        await db.decrement_free_match(partner_id)
        await notify_matched(chat_id, context)
        await notify_matched(partner_id, context)
    else:
        context.job_queue.run_once(
            on_search_timeout, when=SEARCH_TIMEOUT_SECONDS, data=chat_id, name=f"timeout_{chat_id}"
        )


async def on_search_timeout(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    db: Database = context.bot_data["db"]
    user = await db.get_or_create_user(chat_id)
    if user["status"] == "searching":
        await context.bot.send_message(
            chat_id,
            "😕 No one's available right now.\nWant to keep waiting, or try our 🤖 AI Companion "
            "(clearly AI, not a real person) while you wait?",
            reply_markup=kb.waiting_kb(),
        )


async def on_keep_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Still looking for a human match...")
    await q.edit_message_text("🔍 Still searching for a partner...", reply_markup=kb.searching_kb())
    context.job_queue.run_once(
        on_search_timeout, when=SEARCH_TIMEOUT_SECONDS, data=q.message.chat_id, name=f"timeout_{q.message.chat_id}"
    )


async def on_ai_offer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🤖 Pick an AI Companion personality (clearly AI, not a real person):",
        reply_markup=kb.personality_kb(),
    )


async def on_ai_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    personality = q.data.removeprefix("ai_pick_")
    chat_id = q.message.chat_id
    await get_db(context).set_field(chat_id, status="ai_chat")
    context.chat_data["ai_personality"] = personality
    context.chat_data["ai_history"] = []
    label = companion.PERSONALITIES[personality][0]
    await q.edit_message_text(
        f"🤖 Connected to your {label} AI Companion.\nThis is an AI, not a real person.",
        reply_markup=kb.ai_chat_kb(),
    )


async def on_ai_end_to_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    await get_db(context).set_field(chat_id, status="idle")
    context.chat_data.pop("ai_history", None)
    await start_search(chat_id, context, edit=q.edit_message_text)


async def on_ai_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await get_db(context).set_field(q.message.chat_id, status="idle")
    context.chat_data.pop("ai_history", None)
    await q.edit_message_text(HOME_TEXT, reply_markup=kb.home_kb())


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    text = update.effective_message.text
    if not text:
        await update.effective_message.reply_text("🤖 The AI Companion only supports text messages right now.")
        return

    db = get_db(context)
    allowed = await db.check_and_increment_ai_usage(
        update.effective_chat.id, user["is_premium"], companion.FREE_DAILY_LIMIT
    )
    if not allowed:
        await update.effective_message.reply_text(
            f"🔒 You've used today's {companion.FREE_DAILY_LIMIT} free AI Companion messages.\n"
            "Upgrade to Premium for unlimited AI chats."
        )
        return

    history = context.chat_data.setdefault("ai_history", [])
    history.append({"role": "user", "content": text})
    del history[:-10]  # keep last 10 turns only — session memory, not long-term

    api_key = context.bot_data["cfg"].anthropic_api_key
    personality = context.chat_data.get("ai_personality", "friendly")
    try:
        reply = await companion.get_reply(api_key, personality, history)
    except Exception:
        logger.exception("AI companion call failed")
        await update.effective_message.reply_text("⚠️ AI Companion is unavailable right now.")
        return

    history.append({"role": "assistant", "content": reply})
    await update.effective_message.reply_text(reply)


async def on_find_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await start_search(q.message.chat_id, context, edit=q.edit_message_text)


async def on_cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await get_db(context).set_field(q.message.chat_id, status="idle")
    await q.edit_message_text(HOME_TEXT, reply_markup=kb.home_kb())


async def on_end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    partner_id = await get_db(context).end_chat(q.message.chat_id)
    await q.edit_message_text(HOME_TEXT, reply_markup=kb.home_kb())
    if partner_id:
        await context.bot.send_message(partner_id, "❌ Your partner ended the chat.", reply_markup=kb.home_kb())


async def on_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    partner_id = await get_db(context).end_chat(chat_id)
    if partner_id:
        await context.bot.send_message(partner_id, "⏭️ Your partner skipped.", reply_markup=kb.home_kb())
    await start_search(chat_id, context, edit=q.edit_message_text)


async def on_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    db = get_db(context)
    user = await db.get_or_create_user(q.message.chat_id)
    if not user["partner_id"]:
        await q.answer("No active chat to report.", show_alert=True)
        return
    await db.add_report(q.message.chat_id, user["partner_id"])
    await q.answer("Report submitted. Thank you.", show_alert=True)


async def on_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    db = get_db(context)
    chat_id = q.message.chat_id
    user = await db.get_or_create_user(chat_id)
    if not user["partner_id"]:
        await q.answer("No active chat to block.", show_alert=True)
        return
    partner_id = user["partner_id"]
    await db.block_user(chat_id, partner_id)
    await db.end_chat(chat_id)
    await q.answer("User blocked and chat ended.", show_alert=True)
    await q.edit_message_text(HOME_TEXT, reply_markup=kb.home_kb())
    await context.bot.send_message(partner_id, "❌ Chat ended.", reply_markup=kb.home_kb())


async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = get_db(context)
    chat_id = update.effective_chat.id
    user = await db.get_or_create_user(chat_id)

    if user["status"] == "ai_chat":
        await handle_ai_message(update, context, user)
        return

    if user["status"] != "matched" or not user["partner_id"]:
        return
    try:
        await context.bot.copy_message(
            chat_id=user["partner_id"],
            from_chat_id=chat_id,
            message_id=update.effective_message.message_id,
        )
    except TelegramError:
        logger.exception("Failed to forward message")
        await update.effective_message.reply_text("⚠️ Couldn't deliver your message.")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception", exc_info=context.error)


async def on_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("💎 Choose your Premium plan:", reply_markup=kb.premium_kb())


async def on_buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    plan_key = q.data.removeprefix("buy_")
    plan = payments.PLANS[plan_key]
    await context.bot.send_invoice(
        chat_id=q.message.chat_id,
        title=f"Premium — {plan.label}",
        description="Unlimited matches, gender filters, no ads, unlimited AI Companion chats.",
        payload=plan_key,
        provider_token="",  # empty string = Telegram Stars, required for digital goods
        currency="XTR",
        prices=[LabeledPrice(plan.label, plan.stars)],
    )


async def on_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def on_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_key = update.message.successful_payment.invoice_payload
    plan = payments.PLANS.get(plan_key)
    if not plan:
        logger.error("Unknown plan payload: %s", plan_key)
        return
    until = datetime.now(timezone.utc) + plan.duration
    await get_db(context).set_field(
        update.effective_chat.id, is_premium=True, premium_until=until
    )
    await update.message.reply_text(
        f"🎉 Premium activated for {plan.label}! Unlimited matches, gender filters, and AI chats are unlocked."
    )


async def paysupport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Payment issue? Reply here describing what happened. Eligible Stars purchases are refunded in full."
    )
