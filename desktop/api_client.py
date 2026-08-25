# api_client.py
"""
Client API HTTP — équivalent direct de mobile/ScanMobileApp/src/services/api.ts

Endpoints utilisés (préfixe /api/mobile/...) :
  GET  /api/mobile/test/                -> test de connexion
  GET  /api/mobile/sites/               -> liste des sites
  POST /api/mobile/scan/check-first/    -> vérifie l'état d'une garde
  POST /api/mobile/scan/record/         -> enregistre un scan
  GET  /api/mobile/pointages/           -> historique d'un employé (employee_qr requis)
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


def get_api_token() -> str:
    """Jeton de l'opérateur connecté (obtenu par login, jamais provisionné
    manuellement ni codé en dur). Sans ce jeton, les endpoints
    /api/mobile/... répondent 401. Le mot de passe n'est jamais stocké —
    seul ce jeton l'est, comme n'importe quelle clé API."""
    return storage.get("api_token") or ""


def set_api_token(token: str):
    storage.set("api_token", token.strip())


def get_current_user() -> dict | None:
    """Infos de l'opérateur connecté (username/nom), pour affichage
    uniquement. Jamais de mot de passe stocké."""
    return storage.get("current_user")


def is_authenticated() -> bool:
    return bool(get_api_token())


def login(username: str, password: str) -> dict:
    """Authentifie un compte utilisateur Django déjà existant (identique
    au login web/mobile). Ce compte identifie l'OPÉRATEUR du poste
    desktop, jamais l'employé qui sera scanné ensuite — les deux notions
    restent totalement indépendantes dans tout le reste de l'API."""
    try:
        resp = requests.post(
            _url("/api/mobile/auth/login/"),
            json={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        data = _parse_json(resp)
        if data.get("status") != "success":
            raise ApiError(data.get("message", "Identifiants incorrects."))
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Impossible de joindre le serveur : {e}")

    token = data["data"]["token"]
    user = data["data"]["user"]
    storage.set("api_token", token)
    storage.set("current_user", user)
    return user


def logout():
    """Révoque le jeton côté serveur (pas seulement localement) puis purge
    le stockage local. Si le serveur est injoignable, la purge locale a
    lieu quand même : l'opérateur doit pouvoir se déconnecter du poste
    même hors-ligne."""
    try:
        requests.post(_url("/api/mobile/auth/logout/"), headers=_headers(), timeout=TIMEOUT)
    except requests.exceptions.RequestException:
        pass
    finally:
        storage.remove("api_token")
        storage.remove("current_user")


def _headers() -> dict:
    token = get_api_token()
    return {"Authorization": f"Token {token}"} if token else {}


def _url(path: str, base_url_override: str = None) -> str:
    base = base_url_override or get_base_url()
    return f"{base}{path}"


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

def test_connection(base_url: str = None) -> dict:
    """
    Teste la connexion au serveur. Si base_url est fourni, teste CETTE
    URL sans jamais toucher au stockage local (aucun autre écran ne doit
    voir la config bouger pendant qu'on teste une URL candidate). Sans
    base_url, teste l'URL actuellement enregistrée.
    """
    target_url = base_url or get_base_url()
    start = time.time()
    try:
        resp = requests.get(_url("/api/mobile/test/", base_url_override=base_url), timeout=10)
        elapsed_ms = int((time.time() - start) * 1000)
        data = _parse_json(resp)
        if data.get("status") == "success":
            return {"success": True, "message": "Connecté", "url": target_url,
                    "response_time": elapsed_ms}
        return {"success": False, "message": "Réponse inattendue du serveur",
                "url": target_url, "response_time": elapsed_ms}
    except ApiError as e:
        return {"success": False, "message": e.message, "url": target_url,
                "response_time": int((time.time() - start) * 1000)}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "Timeout : le serveur ne répond pas",
                "url": target_url, "response_time": int((time.time() - start) * 1000)}
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Impossible de joindre le serveur ({e})",
                "url": target_url, "response_time": int((time.time() - start) * 1000)}


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
        resp = requests.get(_url("/api/mobile/sites/"), headers=_headers(), timeout=TIMEOUT)
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
            headers=_headers(),
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
            headers=_headers(),
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
            _url("/api/mobile/pointages/today/"), params=params, headers=_headers(), timeout=TIMEOUT
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

def get_employee_pointages(employee_qr: str, date: str = None) -> dict:
    """Historique d'un employé. Nécessite le QR complet (matricule:token) —
    le backend exige une preuve de possession du badge, pas juste le
    matricule."""
    params = {"employee_qr": employee_qr}
    if date:
        params["date"] = date
    try:
        resp = requests.get(_url("/api/mobile/pointages/"), params=params, headers=_headers(), timeout=TIMEOUT)
        data = _parse_json(resp)
        if data.get("status") == "success":
            return data["data"]
        raise ApiError(data.get("message", "Erreur pointages"))
    except ApiError:
        raise
    except requests.exceptions.RequestException as e:
        raise ApiError(f"Impossible de joindre le serveur ({e})") from e
