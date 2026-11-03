import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "telugu-ai-caller"
TARGET_SCRIPT = PROJECT / "scripts" / "migrate_sqlite_to_pg.py"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

spec = importlib.util.spec_from_file_location("telugu_caller_migrate", TARGET_SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["telugu_caller_migrate"] = mod
spec.loader.exec_module(mod)

run_migration = mod.run_migration

if __name__ == "__main__":
    run_migration()
