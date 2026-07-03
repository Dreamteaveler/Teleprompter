import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / "Backup"
TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")

files = [
    "data/teleprompter.db",
    "app/database.py",
    "app/shortcut_manager.py",
    "app/paths.py",
    "app/models.py",
    "app/templates/prompter.html",
    "app/styles/theme.qss",
    "app/pages/__init__.py",
    "app/pages/main_window.py",
    "app/pages/home_page.py",
    "app/pages/editor_page.py",
    "app/pages/prompter_page.py",
    "app/pages/control_panel.py",
    "app/pages/playback_mixin.py",
    "app/pages/mirror_sync_mixin.py",
    "app/pages/mirror_window.py",
]

for f in files:
    src = ROOT / f
    if not src.exists():
        print(f"SKIP: {f}")
        continue
    dst = BACKUP / f"{Path(f).name}_{TIMESTAMP}.bak"
    shutil.copy2(str(src), str(dst))
    print(f"OK: {dst.name}")

print(f"\nDone. Timestamp: {TIMESTAMP}")
