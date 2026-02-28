#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


def run_script(script_path: Path) -> None:
    print(f"Running: {script_path.name}")
    subprocess.run([sys.executable, str(script_path)], check=True)
    print(f"Completed: {script_path.name}\n")


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    scripts_to_run = [
        "BACKEND/AA_check_all_existing.py",
        "BACKEND/AB_update_WHITELIST.py",
        "BACKEND/BA_from_repos_to_TEMP_LIST.py",
        "BACKEND/BB_from_TEMP_LIST_to_TEMP_CHECKED.py",
        "BACKEND/BC_from_TEMP_CHECKED_to_ALL.py",
    ]

    try:
        for script_rel_path in scripts_to_run:
            run_script(project_root / script_rel_path)
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
        return 130
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 130:
            print("\nStopped by user (Ctrl+C).")
            return 130
        print(f"Failed: {exc}")
        return exc.returncode if isinstance(exc.returncode, int) else 1

    print("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
