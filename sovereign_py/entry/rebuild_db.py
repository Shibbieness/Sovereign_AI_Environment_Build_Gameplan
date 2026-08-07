"""
Rebuild the ML Filesystem database from scratch.

Drops any existing SQLite database file at Config.DATABASE_URL, then
re-initializes it via core.database.db.init_db() so all 17 tables (12 base
+ 5 enhanced) get created and the default admin user / tags / training
blocks get seeded.

Usage: python entry/rebuild_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.module_path_bridge  # noqa: E402,F401

from core.config import Config  # noqa: E402
from core.database import db  # noqa: E402


def main():
    db_url = Config.DATABASE_URL
    if db_url.startswith('sqlite:///'):
        db_path = Path(db_url.replace('sqlite:///', '', 1))
        if db_path.exists():
            print(f"→ Removing existing database: {db_path}")
            db_path.unlink()
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"→ Initializing database: {db_url}")
    db.init_db()
    print("✓ Database rebuilt: all tables created, default admin user seeded.")
    print("  Default login: admin / admin")


if __name__ == '__main__':
    main()
