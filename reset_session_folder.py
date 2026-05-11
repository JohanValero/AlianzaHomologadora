import re
import shutil
from pathlib import Path

BACKUP_DIR = Path("./resources/output/backup_llm_answer")
# Pattern: backup_{session_id}_{batch_start}_{batch_end}.json
PATTERN = re.compile(r"^backup_(.+)_(\d+)_(\d+)\.json$")

def parse_filename(filename: str):
    m = PATTERN.match(filename)
    if not m:
        return None
    session_id, batch_start, batch_end = m.group(1), int(m.group(2)), int(m.group(3))
    return session_id, batch_start, batch_end

def reorganize(dry_run: bool = False):
    files = [f for f in BACKUP_DIR.iterdir() if f.is_file() and f.name.endswith(".json")]

    moved, skipped = 0, 0
    for f in sorted(files):
        parsed = parse_filename(f.name)
        if not parsed:
            print(f"[SKIP] Could not parse: {f.name}")
            skipped += 1
            continue

        session_id, batch_start, batch_end = parsed
        dest_dir = BACKUP_DIR / session_id
        dest_file = dest_dir / f"backup_{batch_start}_{batch_end}.json"

        print(f"[{'DRY' if dry_run else 'MOVE'}] {f.name}")
        print(f"        → {dest_file.relative_to(BACKUP_DIR.parent.parent)}")

        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), dest_file)

        moved += 1

    print(f"\nDone. {moved} file(s) {'would be ' if dry_run else ''}moved, {skipped} skipped.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reorganize backup LLM answer files by session_id.")
    parser.add_argument("--dry-run", action="store_true", help="Preview moves without touching files")
    args = parser.parse_args()

    reorganize(dry_run=args.dry_run)