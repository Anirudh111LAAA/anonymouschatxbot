from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row] for row in rows])


def terms_kb():
    return build([("✅ Accept", "terms_accept")])


def gender_kb():
    return build([("👦 Boy", "gender_boy"), ("👧 Girl", "gender_girl")])


def looking_for_kb():
    return build([("👦 Boys", "look_boy"), ("👧 Girls", "look_girl")], [("🌈 Anyone", "look_any")])


def home_kb():
    return build([("🔍 Find Partner", "find_partner")], [("💎 Upgrade to Premium", "premium_menu")])


def premium_kb():
    from payments import PLANS

    rows = [[(f"{p.label} — {p.stars}⭐", f"buy_{key}")] for key, p in PLANS.items()]
    return build(*rows)


def searching_kb():
    return build([("❌ Cancel", "cancel_search")])


def chat_kb():
    return build([("⏭️ Skip", "skip"), ("🛑 End", "end_chat")], [("🚫 Report", "report"), ("⛔ Block", "block")])


def waiting_kb():
    return build([("⏳ Keep Waiting", "keep_waiting")], [("🤖 Try AI Companion", "ai_offer")])


def personality_kb():
    from companion import PERSONALITIES

    rows = [[(label, f"ai_pick_{key}")] for key, (label, _) in PERSONALITIES.items()]
    return build(*rows)


def ai_chat_kb():
    return build([("🔁 Find Human Instead", "ai_end_to_search")], [("🛑 End", "ai_end")])
