import httpx

FREE_DAILY_LIMIT = 5

PERSONALITIES = {
    "friendly": ("😊 Friendly", "You are a warm, friendly AI companion. Keep replies short and casual."),
    "funny": ("😂 Funny", "You are a witty, joke-loving AI companion. Keep replies short and playful."),
    "supportive": ("🤗 Supportive", "You are a kind, supportive AI companion. Listen and encourage. Keep replies short."),
    "study": ("📚 Study Buddy", "You are a focused study-buddy AI companion. Keep replies short and on-topic."),
}

_SAFETY_SUFFIX = (
    " You must always be clearly identifiable as an AI. Never claim or imply you are a real "
    "human, never pretend to have a physical body, and never encourage payment or gifts by "
    "acting hurt, needy, or romantically manipulative."
)


async def get_reply(api_key: str, personality: str, history: list[dict]) -> str:
    system = PERSONALITIES.get(personality, PERSONALITIES["friendly"])[1] + _SAFETY_SUFFIX
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "system": system,
                "messages": history,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(block["text"] for block in data["content"] if block["type"] == "text")
