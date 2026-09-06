from datetime import date

import asyncpg


class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "Database":
        return cls(await asyncpg.create_pool(dsn))

    async def get_or_create_user(self, chat_id: int) -> asyncpg.Record:
        row = await self.pool.fetchrow("SELECT * FROM users WHERE telegram_chat_id = $1", chat_id)
        if row is None:
            await self.pool.execute("INSERT INTO users (telegram_chat_id) VALUES ($1)", chat_id)
            row = await self.pool.fetchrow("SELECT * FROM users WHERE telegram_chat_id = $1", chat_id)
        return row

    async def set_field(self, chat_id: int, **fields) -> None:
        cols = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
        await self.pool.execute(
            f"UPDATE users SET {cols} WHERE telegram_chat_id = $1", chat_id, *fields.values()
        )

    async def find_and_make_match(self, chat_id: int) -> int | None:
        """Atomically finds a compatible, non-blocked partner and pairs both users."""
        async with self.pool.acquire() as conn, conn.transaction():
            me = await conn.fetchrow(
                "SELECT gender, looking_for FROM users WHERE telegram_chat_id = $1 FOR UPDATE", chat_id
            )
            partner = await conn.fetchrow(
                """
                SELECT telegram_chat_id FROM users u
                WHERE status = 'searching' AND telegram_chat_id != $1
                  AND (looking_for = 'any' OR looking_for = $2)
                  AND ($3 = 'any' OR $3 = gender)
                  AND NOT EXISTS (SELECT 1 FROM blocked_users WHERE blocker_id = $1 AND blocked_id = u.telegram_chat_id)
                  AND NOT EXISTS (SELECT 1 FROM blocked_users WHERE blocker_id = u.telegram_chat_id AND blocked_id = $1)
                FOR UPDATE SKIP LOCKED LIMIT 1
                """,
                chat_id, me["gender"], me["looking_for"],
            )
            if partner is None:
                return None
            partner_id = partner["telegram_chat_id"]
            await conn.execute(
                "UPDATE users SET status = 'matched', partner_id = $2 WHERE telegram_chat_id = $1",
                chat_id, partner_id,
            )
            await conn.execute(
                "UPDATE users SET status = 'matched', partner_id = $2 WHERE telegram_chat_id = $1",
                partner_id, chat_id,
            )
            return partner_id

    async def end_chat(self, chat_id: int) -> int | None:
        row = await self.pool.fetchrow("SELECT partner_id FROM users WHERE telegram_chat_id = $1", chat_id)
        partner_id = row["partner_id"] if row else None
        await self.pool.execute(
            "UPDATE users SET status = 'idle', partner_id = NULL WHERE telegram_chat_id = $1", chat_id
        )
        if partner_id:
            await self.pool.execute(
                "UPDATE users SET status = 'idle', partner_id = NULL WHERE telegram_chat_id = $1", partner_id
            )
        return partner_id

    async def decrement_free_match(self, chat_id: int) -> None:
        await self.pool.execute(
            "UPDATE users SET free_matches = free_matches - 1 WHERE telegram_chat_id = $1 AND is_premium = FALSE",
            chat_id,
        )

    async def check_and_increment_ai_usage(self, chat_id: int, is_premium: bool, daily_limit: int) -> bool:
        """Returns True if this AI message is allowed under the free-tier daily cap."""
        if is_premium:
            return True
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT ai_messages_today, ai_last_reset FROM users WHERE telegram_chat_id = $1 FOR UPDATE",
                chat_id,
            )
            used = row["ai_messages_today"]
            if row["ai_last_reset"] != date.today():
                used = 0
                await conn.execute(
                    "UPDATE users SET ai_messages_today = 0, ai_last_reset = CURRENT_DATE WHERE telegram_chat_id = $1",
                    chat_id,
                )
            if used >= daily_limit:
                return False
            await conn.execute(
                "UPDATE users SET ai_messages_today = ai_messages_today + 1 WHERE telegram_chat_id = $1", chat_id
            )
            return True

    async def expire_stale_premium(self) -> None:
        await self.pool.execute(
            "UPDATE users SET is_premium = FALSE WHERE is_premium = TRUE AND premium_until < now()"
        )

    async def add_report(self, reporter: int, reported: int) -> None:
        await self.pool.execute("INSERT INTO reports (reporter, reported) VALUES ($1, $2)", reporter, reported)

    async def block_user(self, blocker: int, blocked: int) -> None:
        await self.pool.execute(
            "INSERT INTO blocked_users (blocker_id, blocked_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            blocker, blocked,
        )
