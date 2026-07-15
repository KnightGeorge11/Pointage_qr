# api_client.py
"""
Client API HTTP — équivalent direct de mobile/ScanMobileApp/src/services/api.ts

Endpoints utilisés (préfixe /api/mobile/...) :
  GET  /api/mobile/test/                -> test de connexion
  GET  /api/mobile/sites/               -> liste des sites
  POST /api/mobile/scan/check-first/    -> vérifie l'état d'une garde
  POST /api/mobile/scan/record/         -> enregistre un scan
  GET  /api/mobile/pointages/           -> historique d'un employé
  GET  /api/mobile/pointages/today/     -> journal du jour (tous les employés)
"""

import time
import requests
import storage

TIMEOUT = 15
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_base_url() -> str:
    return storage.get("api_base_url")


def set_base_url(url: str):
    storage.set("api_base_url", url.strip().rstrip("/"))


def _url(path: str) -> str:
    return f"{get_base_url()}{path}"


class ApiError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _parse_json(resp) -> dict:
    """
    Parse sécurisé : lève ApiError avec un message clair si la réponse
    n'est pas du JSON valide (corps vide, page HTML 404, etc.).
    """
    if not resp.content:
        raise ApiError(
            f"Le serveur a retourné une réponse vide (HTTP {resp.status_code}).\n"
            "Vérifiez l'URL dans les paramètres."
        )
    try:
        return resp.json()
    except ValueError:
        preview = resp.text[:120].strip()
        raise ApiError(
            f"Réponse non-JSON du serveur (HTTP {resp.status_code}).\n"
            f"Aperçu : {preview}\n"
            "Vérifiez l'URL dans les paramètres."
        ) from None


# ============================================================
# Connexion
# ============================================================

def test_connection() -> dict:
    start = time.time()
    try:
        resp = requests.get(_url("/api/mobile/test/"), timeout=10)
        elapsed_ms = int((time.time() - start) * 1000)
        data = _parse_json(resp)
        if data.get("status") == "success":
            return {"success": True, "message": "Connecté", "url": get_base_url(),
                    "response_time": elapsed_ms}
        return {"success": False, "message": "Réponse inattendue du serveur",
                "url": get_base_url(), "response_time": elapsed_ms}
    except ApiError as e:
        return {"success": False, "message": e.message, "url": get_base_url(),
                "response_time": int((time.time() - start) * 1000)}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Timeout : le serveur ne répond pas",
                "url": get_base_url(), "response_time": int((time.time() - start) * 1000)}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Impossible de joindre le serveur ({e})",
                "url": get_base_url(), "response_time": int((time.time() - start) * 1000)}


def check_status() -> dict:
    result = test_connection()
    return {"connected": result["success"], "base_url": get_base_url()}


# ============================================================
# Sites
# ============================================================

def get_sites(force_refresh: bool = False) -> list:
    cached_sites = storage.get("cached_sites")
    cache_ts = storage.get("cached_sites_timestamp")
    cache_valid = cache_ts and (time.time() * 1000 - cache_ts) < CACHE_TTL_SECONDS * 1000

    if cached_sites and cache_valid and not force_refresh:
        return cached_sites

    try:
        resp = requests.get(_url("/api/mobile/sites/"), timeout=TIMEOUT)
        data = _parse_json(resp)
        if data.get("status") == "success" and isinstance(data.get("data"), list):
            sites = data["data"]
            storage.set("cached_sites", sites)
            storage.set("cached_sites_timestamp", time.time() * 1000)
            return sites
        raise ApiError(data.get("message", "Erreur récupération des sites"))
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        if cached_sites:
            return cached_sites
        raise ApiError(f"Impossible de joindre le serveur ({e})") from e


def sync_sites() -> list:
    storage.set("cached_sites", None)
    storage.set("cached_sites_timestamp", None)
    return get_sites(force_refresh=True)


# ============================================================
# Site sélectionné (local)
# ============================================================

def save_selected_site(site: dict):
    storage.set("selected_site", site)


def get_selected_site():
    return storage.get("selected_site")


def clear_selected_site():
    storage.set("selected_site", None)


# ============================================================
# Scan
# ============================================================

def check_first_scan(employee_qr: str, site_id: int) -> dict:
    try:
        resp = requests.post(
            _url("/api/mobile/scan/check-first/"),
            json={"employee_qr": employee_qr, "site_id": site_id},
            timeout=TIMEOUT,
        )
        data = _parse_json(resp)
        if not resp.ok:
            raise ApiError(data.get("message", "Impossible de vérifier l'état des gardes"))
        if not data.get("data"):
            raise ApiError("Réponse API invalide")
        return data["data"]
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Erreur réseau ({e})") from e


def record_scan(employee_qr: str, site_id: int, mode: str,
                force_new: bool = False) -> dict:
    try:
        resp = requests.post(
            _url("/api/mobile/scan/record/"),
            json={
                "employee_qr": employee_qr,
                "site_id":     site_id,
                "mode":        mode,
                "force_new":   force_new,
            },
            timeout=TIMEOUT,
        )
        data = _parse_json(resp)
        return {"ok": resp.ok, "data": data}
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Impossible de contacter le serveur ({e})") from e


# ============================================================
# Journal du jour — tous les pointages (vue superviseur)
# ============================================================

def get_today_pointages(site_id: int = None, date: str = None) -> dict:
    """
    Retourne tous les pointages d'une journée.
    Endpoint : GET /api/mobile/pointages/today/?site_id=N&date=YYYY-MM-DD
    Retourne  : {'status': 'success', 'date': ..., 'count': N, 'data': [...]}
    """
    params = {}
    if site_id:
        params["site_id"] = site_id
    if date:
        params["date"] = date
    try:
        resp = requests.get(
            _url("/api/mobile/pointages/today/"), params=params, timeout=TIMEOUT
        )
        data = _parse_json(resp)
        if data.get("status") == "success":
            return data
        raise ApiError(data.get("message", "Erreur récupération des pointages du jour"))
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Impossible de joindre le serveur ({e})") from e


# ============================================================
# Historique personnel d'un employé
# ============================================================

def get_employee_pointages(matricule: str, date: str = None) -> dict:
    params = {"matricule": matricule}
    if date:
        params["date"] = date
    try:
        resp = requests.get(_url("/api/mobile/pointages/"), params=params, timeout=TIMEOUT)
        data = _parse_json(resp)
        if data.get("status") == "success":
            return data["data"]
        raise ApiError(data.get("message", "Erreur pointages"))
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Impossible de joindre le serveur ({e})") from e
