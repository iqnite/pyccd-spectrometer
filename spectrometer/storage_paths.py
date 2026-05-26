from __future__ import annotations

import shutil
import sys
from pathlib import Path


APP_NAME = "pySPEC"


def get_app_data_dir() -> Path:
    """Return a writable directory for application state."""
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path.home() / ".config"

    app_dir = base_dir / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_settings_path(filename: str) -> Path:
    """Return the writable settings path for a given filename."""
    return get_app_data_dir() / filename


def migrate_legacy_file(filename: str) -> Path:
    """Move a legacy project-root file into the writable app-data directory."""
    target_path = get_settings_path(filename)
    if target_path.exists():
        return target_path

    legacy_path = Path.cwd() / filename
    if legacy_path.exists():
        try:
            shutil.copy2(legacy_path, target_path)
        except OSError:
            pass

    return target_path