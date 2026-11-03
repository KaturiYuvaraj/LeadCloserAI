import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "telugu-ai-caller"
VENV_SITE = PROJECT / "venv" / "Lib" / "site-packages"
TARGET_SCRIPT = PROJECT / "scripts" / "migrate_sqlite_to_pg.py"

for p in [str(PROJECT), str(VENV_SITE), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location("telugu_caller_migrate", TARGET_SCRIPT)
if spec and spec.loader:
    mod = importlib.util.module_from_spec(spec)
    sys.modules["telugu_caller_migrate"] = mod
    spec.loader.exec_module(mod)
    run_migration = mod.run_migration
else:
    raise ImportError(f"Could not load migration module from {TARGET_SCRIPT}")

if __name__ == "__main__":
    run_migration()
