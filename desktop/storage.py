# storage.py
"""
Stockage local persistant pour l'application desktop.
Équivalent du AsyncStorage utilisé dans l'application mobile React Native.
Les données sont sauvegardées dans un fichier JSON situé dans le dossier
utilisateur (~/.pointage_qr_desktop/settings.json).
"""

import json
import logging
from pathlib import Path

APP_DIR = Path.home() / ".pointage_qr_desktop"
SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULTS = {
    "api_base_url": "http://pointageqr.local:8000",
    "selected_site": None,        # dict {id, nom, adresse, ...}
    "user_matricule": None,       # str
    "cached_sites": None,         # list[dict]
    "cached_sites_timestamp": None,
}


def _ensure_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def _load_all() -> dict:
    _ensure_dir()
    if not SETTINGS_FILE.exists():
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        logging.error(f"Erreur lors du chargement des paramètres : {e}")
        return dict(DEFAULTS)


def _save_all(data: dict):
    _ensure_dir()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(key: str):
    return _load_all().get(key, DEFAULTS.get(key))


def set(key: str, value):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("La clé doit être une chaîne non vide.")
    data = _load_all()
    data[key] = value
    _save_all(data)


def remove(key: str):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("La clé doit être une chaîne non vide.")
    data = _load_all()
    data[key] = None
    _save_all(data)
