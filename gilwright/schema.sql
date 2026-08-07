-- GILWRIGHT DATABASE SCHEMA — gilwright.db
-- Source: gilwright skill codex/database-schema.md, v0u1p0
-- Seventh stack SQLite database. SQLite because the factory is local-first
-- like everything else in the stack.

PRAGMA foreign_keys = ON;

CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  lifecycle TEXT NOT NULL DEFAULT 'amorphous'
    CHECK (lifecycle IN ('amorphous','ice','crystal','void')),
  source TEXT,                -- stack origin (e.g. 'lattice', 'net-new')
  channel TEXT,               -- gumroad | itchio | github | other
  price_usd REAL,
  vup TEXT DEFAULT 'v0u1p0',
  created_at TEXT DEFAULT (datetime('now')),
  voided_at TEXT,
  ghost_bone INTEGER DEFAULT 0  -- 1 = voided but still depended on
);

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY,
  started_at TEXT DEFAULT (datetime('now')),
  product_id INTEGER REFERENCES products(id),
  task_summary TEXT NOT NULL,
  clean_boundary INTEGER NOT NULL DEFAULT 1,  -- 0 = cut off; continue-skill applies
  commit_hash TEXT
);

CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id),
  title TEXT NOT NULL,
  spec TEXT,                  -- the bridge wire format entry
  block_type TEXT,            -- annotation only
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','active','done','void')),
  acceptance TEXT,            -- how Wright knows it's done
  created_at TEXT DEFAULT (datetime('now')),
  done_at TEXT
);

CREATE TABLE artifacts (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id),
  path TEXT NOT NULL,         -- repo-relative
  kind TEXT CHECK (kind IN ('src','dist','flavor','hands','doc')),
  vanilla_certified INTEGER DEFAULT 0,  -- Scrubber sets 1 (dist/ only)
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE hands_queue (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES products(id),
  action TEXT NOT NULL,       -- click-level, no judgment required
  ordinal INTEGER NOT NULL,
  done INTEGER DEFAULT 0,
  done_at TEXT
);

-- NADA_PROTECTED: append-only. No UPDATE, no DELETE. Corrections are new rows
-- with sign flipped and note set. Enforced by triggers below.
CREATE TABLE ledger (
  id INTEGER PRIMARY KEY,
  at TEXT DEFAULT (datetime('now')),
  product_id INTEGER REFERENCES products(id),
  kind TEXT NOT NULL CHECK (kind IN
    ('usage_estimate','channel_fee','revenue','refund','correction','seed_capital')),
  amount_usd REAL NOT NULL,   -- negative = cost, positive = income
  note TEXT
);
CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is NADA_PROTECTED: append-only'); END;
CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is NADA_PROTECTED: append-only'); END;

CREATE VIEW ledger_summary AS
  SELECT p.name, p.lifecycle,
         ROUND(SUM(CASE WHEN l.amount_usd > 0 THEN l.amount_usd ELSE 0 END),2) AS income,
         ROUND(SUM(CASE WHEN l.amount_usd < 0 THEN l.amount_usd ELSE 0 END),2) AS cost,
         ROUND(SUM(l.amount_usd),2) AS net
  FROM ledger l LEFT JOIN products p ON p.id = l.product_id
  GROUP BY l.product_id;
