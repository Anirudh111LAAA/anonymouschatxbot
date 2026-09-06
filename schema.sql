CREATE TABLE IF NOT EXISTS users (
    telegram_chat_id BIGINT PRIMARY KEY,
    gender TEXT,
    looking_for TEXT,
    status TEXT NOT NULL DEFAULT 'idle',   -- idle | searching | matched
    partner_id BIGINT,
    free_matches INT NOT NULL DEFAULT 15,
    is_premium BOOLEAN NOT NULL DEFAULT FALSE,
    premium_until TIMESTAMPTZ,
    accepted_terms BOOLEAN NOT NULL DEFAULT FALSE,
    ai_messages_today INT NOT NULL DEFAULT 0,
    ai_last_reset DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safe to re-run on an existing DB from before the AI companion feature:
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_messages_today INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_last_reset DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    reporter BIGINT NOT NULL,
    reported BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS blocked_users (
    blocker_id BIGINT NOT NULL,
    blocked_id BIGINT NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id)
);
