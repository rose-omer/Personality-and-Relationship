-- 002: Paylaşılabilir sonuçlar ve kalıcı çift oturumları. İçerik schema.sql ile aynıdır.
-- Geri alma: 002_results_and_couple_sessions.down.sql
BEGIN;
CREATE TABLE IF NOT EXISTS results (
    share_id   text PRIMARY KEY,
    nickname   text CHECK (char_length(nickname) <= 40),
    answers    jsonb NOT NULL,
    result     jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS results_expires_at_idx ON results (expires_at);

CREATE TABLE IF NOT EXISTS couple_sessions (
    id         uuid PRIMARY KEY,
    name1      text NOT NULL CHECK (char_length(name1) BETWEEN 1 AND 40),
    name2      text NOT NULL CHECK (char_length(name2) BETWEEN 1 AND 40),
    answers1   jsonb,
    answers2   jsonb,
    status     text NOT NULL DEFAULT 'bekliyor'
               CHECK (status IN ('bekliyor', 'analiz', 'hazir', 'hata')),
    result     jsonb,
    share_id   text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS couple_sessions_expires_at_idx ON couple_sessions (expires_at);
COMMIT;
