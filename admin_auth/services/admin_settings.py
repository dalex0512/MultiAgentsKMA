import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SETTINGS_PATH = _DATA_DIR / "admin_settings.json"

_DEFAULT = {
    "disabled_agents": [],
    "maintenance_message": "",
}


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    _ensure_dir()
    if not _SETTINGS_PATH.exists():
        return dict(_DEFAULT)
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULT, **data}
    except Exception:
        return dict(_DEFAULT)


def save_settings(data: dict) -> dict:
    _ensure_dir()
    merged = {**_DEFAULT, **data}
    _SETTINGS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return merged
