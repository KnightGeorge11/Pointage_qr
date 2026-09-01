# storage.py
"""
Stockage local persistant pour l'application desktop.
Équivalent du AsyncStorage utilisé dans l'application mobile React Native.
Les préférences non sensibles sont sauvegardées dans un fichier JSON situé
 dans le dossier utilisateur (~/.pointage_qr_desktop/settings.json).

Le jeton d'authentification n'est volontairement PLUS stocké dans ce JSON :
il est conservé dans le gestionnaire d'identifiants du système via keyring.
"""

import json
import logging
from pathlib import Path

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

APP_DIR = Path.home() / ".pointage_qr_desktop"
SETTINGS_FILE = APP_DIR / "settings.json"
KEYRING_SERVICE = "PointageQR-Desktop"
TOKEN_KEY = "api_token"

DEFAULTS = {
    "api_base_url": "http://pointageqr.local:8000",
    "current_user": None,
    "selected_site": None,
    "user_matricule": None,
    "cached_sites": None,
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
        merged.pop(TOKEN_KEY, None)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        logging.error("Erreur lors du chargement des paramètres : %s", e)
        return dict(DEFAULTS)


def _save_all(data: dict):
    _ensure_dir()
    safe_data = dict(data)
    safe_data.pop(TOKEN_KEY, None)
    temporary_file = SETTINGS_FILE.with_suffix(".tmp")
    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(safe_data, f, ensure_ascii=False, indent=2)
    temporary_file.replace(SETTINGS_FILE)


def _legacy_token() -> str | None:
    """Lit une seule fois un ancien token JSON pour migration."""
    if not SETTINGS_FILE.exists():
        return None
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        token = raw.get(TOKEN_KEY)
        return token.strip() if isinstance(token, str) and token.strip() else None
    except (json.JSONDecodeError, OSError):
        return None


def _get_token() -> str | None:
    try:
        username = "scanner"
        token = keyring.get_password(KEYRING_SERVICE, username)
        if token:
            return token

        legacy = _legacy_token()
        if legacy:
            keyring.set_password(KEYRING_SERVICE, username, legacy)
            _save_all(_load_all())
            return legacy
    except KeyringError as exc:
        logging.warning("Gestionnaire d'identifiants indisponible : %s", exc)
    return None


def _set_token(value: str | None):
    username = "scanner"
    try:
        if value is None or not str(value).strip():
            try:
                keyring.delete_password(KEYRING_SERVICE, username)
            except PasswordDeleteError:
                pass
        else:
            keyring.set_password(KEYRING_SERVICE, username, str(value).strip())

        # Supprime systématiquement toute ancienne copie en clair.
        _save_all(_load_all())
    except KeyringError as exc:
        raise RuntimeError(
            "Impossible de sécuriser le jeton dans le gestionnaire d'identifiants du système."
        ) from exc


def get(key: str):
    if key == TOKEN_KEY:
        return _get_token()
    return _load_all().get(key, DEFAULTS.get(key))


def set(key: str, value):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("La clé doit être une chaîne non vide.")
    if key == TOKEN_KEY:
        _set_token(value)
        return
    data = _load_all()
    data[key] = value
    _save_all(data)


def remove(key: str):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("La clé doit être une chaîne non vide.")
    if key == TOKEN_KEY:
        _set_token(None)
        return
    data = _load_all()
    data[key] = None
    _save_all(data)
