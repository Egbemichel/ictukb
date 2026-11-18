-- Key-value store for the WhatsApp listener (linked-device session and post bookkeeping).
CREATE TABLE IF NOT EXISTS wa_state (
  key        text PRIMARY KEY,
  value      text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
