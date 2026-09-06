import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    admin_ids: set[int]
    anthropic_api_key: str


def load_config() -> Config:
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        database_url=os.environ["DATABASE_URL"],
        admin_ids={int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x},
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
    )
