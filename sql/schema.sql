CREATE TABLE IF NOT EXISTS holdings (
  id          SERIAL PRIMARY KEY,
  user_id     TEXT NOT NULL,
  symbol      TEXT NOT NULL,          -- ticker, or CASH
  name        TEXT,                   -- full name, e.g. "Vanguard Total Stock Market ETF"
  quantity    NUMERIC NOT NULL,       -- for CASH: the amount
  avg_cost    NUMERIC NOT NULL,       -- purchase price (fallback when no market price is available)
  asset_class TEXT NOT NULL CHECK (asset_class IN ('equity', 'bond', 'cash'))
);

CREATE TABLE IF NOT EXISTS jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending',   -- pending | running | completed | failed | blocked
  request         JSONB NOT NULL,
  progress        JSONB NOT NULL DEFAULT '[]',       -- graph steps finished so far (shown live in the UI)
  report          TEXT,
  facts           JSONB,          -- exactly what the tools returned (ground truth for the report)
  judge_score     NUMERIC,
  judge_criteria  JSONB,
  judge_notes     TEXT,
  revisions       INT DEFAULT 0,
  error           TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE holdings ADD COLUMN IF NOT EXISTS name TEXT;   -- for databases created before names existed

-- demo portfolio
DELETE FROM holdings WHERE user_id = 'demo';
INSERT INTO holdings (user_id, symbol, name, quantity, avg_cost, asset_class) VALUES
  ('demo', 'VTI',  'Vanguard Total Stock Market ETF', 50,   210.00, 'equity'),
  ('demo', 'AAPL', 'Apple Inc.',                      10,   150.00, 'equity'),
  ('demo', 'BND',  'Vanguard Total Bond Market ETF',  40,    72.00, 'bond'),
  ('demo', 'CASH', 'Cash',                            8000,   1.00, 'cash');
