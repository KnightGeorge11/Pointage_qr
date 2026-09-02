import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { DEFAULT_API_URL, STORAGE_KEYS } from '../utils/constants';

export interface Site {
  id: number;
  nom: string;
  adresse?: string;
  heure_ouverture_matin?: string;
  heure_fermeture_matin?: string;
  heure_ouverture_apres_midi?: string;
  heure_fermeture_apres_midi?: string;
}

export interface Employee {
  id: number;
  nom_complet: string;
  matricule: string;
  poste?: string;
}

export interface ApiResponse {
  status: 'success' | 'error';
  message?: string;
  data: any;
}

export interface ApiStatus {
  connected: boolean;
  baseUrl: string;
  lastCheck?: Date | null;
  environment?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message?: string;
  url?: string;
  responseTime?: number;
}

export interface CheckFirstScanResponse {
  prochain_scan?: string;
  mode_attendu?: string;
  first_scan?: boolean;
  periode?: string;
  date?: string;
  garde_planifiee?: boolean;
  garde_en_cours?: {
    id: number;
    date_pointage: string;
    heure_arrivee: string;
  };
  employe: Employee;
  site: {
    id: number;
    nom: string;
  };
}

export interface TodayPointage {
  id: number;
  employe_nom: string;
  employe_matricule: string;
  employe_poste?: string;
  site?: string;
  site_id?: number;
  date_pointage: string;
  periode: 'matin' | 'apres_midi' | 'nuit';
  type_journee: 'normal' | 'garde';
  heure_arrivee?: string;
  heure_depart?: string;
  retard?: string;
  heures_travaillees?: string;
  statut: string;
}

const getBaseUrl = async (): Promise<string> => {
  try {
    const stored = await AsyncStorage.getItem(STORAGE_KEYS.API_URL);
    return stored || DEFAULT_API_URL;
  } catch {
    return DEFAULT_API_URL;
  }
};

// Jeton de l'opérateur connecté (obtenu par login, jamais provisionné
// manuellement ni codé en dur). Sans ce jeton, les endpoints
// /api/mobile/... répondent 401. Le mot de passe n'est jamais stocké —
// seul ce jeton l'est, comme n'importe quelle clé API.
const getScannerToken = async (): Promise<string | null> => {
  try {
    return await AsyncStorage.getItem(STORAGE_KEYS.API_TOKEN);
  } catch {
    return null;
  }
};

export const setScannerToken = async (token: string): Promise<void> => {
  await AsyncStorage.setItem(STORAGE_KEYS.API_TOKEN, token.trim());
  await refreshApi();
};

export interface CurrentUser {
  username: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
}

export const getCurrentUser = async (): Promise<CurrentUser | null> => {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.CURRENT_USER);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

/** Purge complète de l'authentification locale (token + infos utilisateur).
 * Jamais de mot de passe à effacer : il n'est jamais stocké. */
export const clearAuth = async (): Promise<void> => {
  await AsyncStorage.multiRemove([STORAGE_KEYS.API_TOKEN, STORAGE_KEYS.CURRENT_USER]);
  await refreshApi();
};

const createApi = (baseURL: string, token: string | null) => {
  const instance = axios.create({
    baseURL,
    timeout: 15000,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Token ${token}` } : {}),
    },
  });

  // Installer l'intercepteur sur CHAQUE nouvelle instance. refreshApi()
  // recrée l'instance après login/logout/changement d'URL : l'ancien code
  // n'attachait l'intercepteur qu'à l'instance initiale, ce qui faisait
  // perdre la normalisation des erreurs réseau après un refresh.
  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (!error.response) {
        if (error.code === 'ECONNABORTED') {
          error.message = 'Timeout : le serveur ne répond pas';
        } else {
          error.message = 'Impossible de joindre le serveur';
        }
      } else if (error.response.status === 401) {
        error.message = error.response.data?.message || 'Session expirée. Veuillez vous reconnecter.';
      }
      return Promise.reject(error);
    }
  );

  return instance;
};

let api = createApi(DEFAULT_API_URL, null);

const refreshApi = async () => {
  const url = await getBaseUrl();
  const token = await getScannerToken();
  api = createApi(url, token);
};

export const testConnection = async (overrideUrl?: string): Promise<ConnectionTestResult> => {
  // Si overrideUrl est fourni (candidat pas encore enregistré, saisi dans
  // ConfigScreen), on teste CETTE url directement sans jamais toucher à
  // l'instance axios partagée — comme côté desktop, aucun autre écran ne
  // doit voir la config bouger tant que ce n'est pas confirmé par
  // "Sauvegarder".
  const targetUrl = (overrideUrl || api.defaults.baseURL || DEFAULT_API_URL).replace(/\/+$/, '');
  const startTime = Date.now();
  try {
    const response = overrideUrl
      ? await axios.get(`${targetUrl}/api/mobile/test/`, { timeout: 10000 })
      : await api.get('/api/mobile/test/', { timeout: 10000 });
    const responseTime = Date.now() - startTime;
    if (response.data?.status === 'success') {
      return { success: true, message: 'Connecté', url: targetUrl, responseTime };
    }
    return { success: false, message: 'Réponse inattendue du serveur', url: targetUrl, responseTime };
  } catch (error: any) {
    return {
      success: false,
      message: error.message || 'Erreur inconnue',
      url: targetUrl,
      responseTime: Date.now() - startTime,
    };
  }
};

export const checkStatus = async (): Promise<ApiStatus> => {
  const result = await testConnection();
  return {
    connected: result.success,
    baseUrl: api.defaults.baseURL || DEFAULT_API_URL,
    lastCheck: new Date(),
  };
};

export const initializeApi = async (): Promise<boolean> => {
  await refreshApi();
  const result = await testConnection();
  return result.success;
};

export const setBaseUrl = async (url: string): Promise<void> => {
  const cleanUrl = url.replace(/\/+$/, '');
  await AsyncStorage.setItem(STORAGE_KEYS.API_URL, cleanUrl);
  await refreshApi();
};

export const getCurrentServerUrl = (): string => {
  return api.defaults.baseURL || DEFAULT_API_URL;
};

export const apiService = {
  initialize: initializeApi,
  testConnection,
  checkStatus,
  setBaseUrl,
  getCurrentServerUrl,
  getCurrentUser,

  /**
   * Connecte un compte utilisateur Django déjà existant. Le compte
   * connecté (opérateur de l'app) reste totalement distinct de l'employé
   * qui sera scanné ensuite — ce login n'identifie jamais un employé.
   * Ne stocke jamais le mot de passe, uniquement le jeton retourné.
   */
  async login(username: string, password: string): Promise<CurrentUser> {
    const response = await api.post('/api/mobile/auth/login/', { username, password });
    if (response.data.status !== 'success') {
      throw new Error(response.data.message || 'Erreur de connexion');
    }
    const { token, user } = response.data.data;
    if (!token || !user) {
      throw new Error('Réponse d\'authentification invalide');
    }
    await AsyncStorage.setItem(STORAGE_KEYS.CURRENT_USER, JSON.stringify(user));
    await setScannerToken(token);
    return user;
  },

  /**
   * Révoque le jeton côté serveur (pas seulement localement) puis purge
   * le stockage local. Un jeton révoqué est immédiatement refusé par le
   * serveur sur tout appel ultérieur, même s'il était encore en mémoire
   * ailleurs.
   */
  async logout(): Promise<void> {
    try {
      await api.post('/api/mobile/auth/logout/');
    } catch {
      // Même si l'appel réseau échoue (serveur injoignable), on purge
      // quand même localement : l'utilisateur doit pouvoir se déconnecter
      // de l'appareil même hors-ligne.
    } finally {
      await clearAuth();
    }
  },

  /** Vrai uniquement si un jeton ET des infos utilisateur sont stockés localement. */
  async isAuthenticated(): Promise<boolean> {
    const token = await getScannerToken();
    const user = await getCurrentUser();
    return Boolean(token && user?.username);
  },

  async isServerAvailable(): Promise<boolean> {
    const result = await testConnection();
    return result.success;
  },

  async getSites(): Promise<Site[]> {
    const cachedSites = await AsyncStorage.getItem(STORAGE_KEYS.CACHED_SITES);
    const cacheTimestamp = await AsyncStorage.getItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP);
    const cacheValid = cacheTimestamp && Date.now() - parseInt(cacheTimestamp) < 300_000;

    if (cachedSites && cacheValid) {
      return JSON.parse(cachedSites);
    }

    try {
      const response = await api.get<ApiResponse>('/api/mobile/sites/');
      if (response.data.status === 'success' && Array.isArray(response.data.data)) {
        const sites: Site[] = response.data.data;
        await AsyncStorage.setItem(STORAGE_KEYS.CACHED_SITES, JSON.stringify(sites));
        await AsyncStorage.setItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP, Date.now().toString());
        return sites;
      }
      throw new Error(response.data.message || 'Erreur récupération des sites');
    } catch (error: any) {
      if (cachedSites) {
        return JSON.parse(cachedSites);
      }
      throw error;
    }
  },

  async syncSites(): Promise<Site[]> {
    await AsyncStorage.removeItem(STORAGE_KEYS.CACHED_SITES);
    await AsyncStorage.removeItem(STORAGE_KEYS.CACHED_SITES_TIMESTAMP);
    return this.getSites();
  },

  async checkFirstScan(matricule: string, siteId: number): Promise<CheckFirstScanResponse> {
    const response = await api.post<ApiResponse>('/api/mobile/scan/check-first/', {
      employee_qr: matricule,
      site_id: siteId,
    });
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur vérification scan');
  },

  async recordScan(
    employeeQr: string, siteId: number, mode: 'day' | 'night' = 'day',
    options: { forceNew?: boolean; } = {}
  ): Promise<any> {
    const uuidv4 = (): string => {
      const bytes = Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
      bytes[6] = (bytes[6] & 0x0f) | 0x40; bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = bytes.map(b => b.toString(16).padStart(2, '0')).join('');
      return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
    };
    const payload = { employee_qr: employeeQr, site_id: siteId, mode, force_new: options.forceNew ?? false, client_event_id: uuidv4(), captured_at: new Date().toISOString() };
    try {
      const response = await api.post('/api/mobile/scan/record/', payload);
      await this.syncPendingScans(); return response.data;
    } catch (error: any) {
      if (!error.response) {
        const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS);
        const pending = raw ? JSON.parse(raw) : []; pending.push(payload);
        await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify(pending));
        return { status: 'success', code: 'SCAN_HORS_LIGNE', message: 'Scan enregistré localement. Il sera synchronisé dès le retour du réseau.', data: { offline: true } };
      }
      throw error;
    }
  },

  async getPendingScanCount(): Promise<number> {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS); const queue = raw ? JSON.parse(raw) : [];
    return Array.isArray(queue) ? queue.length : 0;
  },

  async syncPendingScans(): Promise<{ synced: number; remaining: number }> {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_SCANS);
    const queue = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(queue) || queue.length === 0) return { synced: 0, remaining: 0 };

    const remaining: any[] = [];
    let synced = 0;
    for (const item of queue) {
      try {
        const response = await api.post('/api/mobile/scan/record/', item);
        if (response.data?.status === 'success') {
          synced++;
        } else {
          remaining.push(item);
        }
      } catch (error: any) {
        if (!error.response) {
          remaining.push(item);
          break;
        }
        const status = error.response.status;
        const retryable = status === 401 || status === 408 || status === 409 || status === 429 || status >= 500;
        if (retryable) {
          remaining.push(item);
          break;
        }
        // Permanent business/validation rejection: do not retry forever.
      }
    }
    await AsyncStorage.setItem(STORAGE_KEYS.PENDING_SCANS, JSON.stringify(remaining));
    return { synced, remaining: remaining.length };
  },

  async getCurrentPeriod(): Promise<any> {
    const response = await api.get<ApiResponse>('/api/mobile/periods/current/');
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur période');
  },

  async saveSelectedSite(site: Site): Promise<void> {
    await AsyncStorage.setItem(STORAGE_KEYS.SELECTED_SITE, JSON.stringify(site));
  },

  async getSelectedSite(): Promise<Site | null> {
    const str = await AsyncStorage.getItem(STORAGE_KEYS.SELECTED_SITE);
    return str ? JSON.parse(str) : null;
  },

  async clearSelectedSite(): Promise<void> {
    await AsyncStorage.removeItem(STORAGE_KEYS.SELECTED_SITE);
  },

  /**
   * Historique d'un employé pour une date donnée. Nécessite le QR complet
   * (matricule:token), pas juste le matricule — le backend exige une preuve
   * de possession du badge, pour éviter qu'un jeton d'appareil scanner
   * suffise à lire les données RH de n'importe quel employé.
   */
  async getEmployeePointages(employeeQr: string, date?: string): Promise<any> {
    let url = `/api/mobile/pointages/?employee_qr=${encodeURIComponent(employeeQr)}`;
    if (date) url += `&date=${date}`;
    const response = await api.get(url);
    if (response.data.status === 'success') return response.data.data;
    throw new Error(response.data.message || 'Erreur pointages');
  },

  async getTodayPointages(siteId?: number | null, date?: string): Promise<{
    count: number;
    date: string;
    data: TodayPointage[];
  }> {
    let url = '/api/mobile/pointages/today/';
    const params: string[] = [];
    if (siteId) params.push(`site_id=${siteId}`);
    if (date)   params.push(`date=${date}`);
    if (params.length) url += '?' + params.join('&');
    const response = await api.get(url);
    if (response.data.status === 'success') return response.data;
    throw new Error(response.data.message || 'Erreur journal du jour');
  },

  async getServerStatus(): Promise<{ status: string; timestamp: string }> {
    try {
      const response = await api.get('/api/mobile/test/');
      return { status: response.data.status, timestamp: new Date().toISOString() };
    } catch {
      return { status: 'offline', timestamp: new Date().toISOString() };
    }
  },
};

export { api, getBaseUrl };
