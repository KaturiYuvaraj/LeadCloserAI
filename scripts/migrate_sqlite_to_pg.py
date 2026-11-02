import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "telugu-ai-caller"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.migrate_sqlite_to_pg import run_migration

if __name__ == "__main__":
    run_migration()
